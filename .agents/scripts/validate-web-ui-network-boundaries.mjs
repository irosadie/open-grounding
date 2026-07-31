import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const repoRoot = path.resolve(import.meta.dirname, '../..');
const uiRoots = [
  path.join(repoRoot, 'apps/web/app'),
  path.join(repoRoot, 'apps/web/components'),
];
const apiRouteRoot = path.join(repoRoot, 'apps/web/app/api');
const sourceExtensions = new Set(['.ts', '.tsx']);
const testFilePattern = /\.(?:test|spec)\.tsx?$/;
const violations = [];
let checkedFileCount = 0;

function listSourceFiles(directoryPath) {
  const files = [];

  for (const entry of readdirSync(directoryPath, { withFileTypes: true })) {
    const entryPath = path.join(directoryPath, entry.name);

    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entryPath === apiRouteRoot) {
        continue;
      }
      files.push(...listSourceFiles(entryPath));
      continue;
    }

    if (entry.isFile() && sourceExtensions.has(path.extname(entry.name)) && !testFilePattern.test(entry.name)) {
      files.push(entryPath);
    }
  }

  return files;
}

function addViolation(sourceFile, node, message) {
  const position = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
  violations.push({
    file: path.relative(repoRoot, sourceFile.fileName),
    line: position.line + 1,
    column: position.character + 1,
    message,
  });
}

function isAxiosModuleSpecifier(node) {
  return (
    ts.isStringLiteral(node) &&
    (node.text === 'axios' || node.text.startsWith('axios/'))
  );
}

function isGlobalFetchCall(expression) {
  if (ts.isIdentifier(expression)) {
    return expression.text === 'fetch';
  }

  if (!ts.isPropertyAccessExpression(expression) || expression.name.text !== 'fetch') {
    return false;
  }

  return (
    ts.isIdentifier(expression.expression) &&
    ['globalThis', 'global', 'window', 'self'].includes(expression.expression.text)
  );
}

function isAxiosRequestCall(expression) {
  if (ts.isIdentifier(expression)) {
    return expression.text === 'axios';
  }

  return ts.isPropertyAccessExpression(expression) && ts.isIdentifier(expression.expression) && expression.expression.text === 'axios';
}

function validateSourceFile(filePath) {
  const sourceFile = ts.createSourceFile(
    filePath,
    readFileSync(filePath, 'utf8'),
    ts.ScriptTarget.Latest,
    true,
    filePath.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );

  checkedFileCount += 1;

  function visit(node) {
    if (ts.isImportDeclaration(node) && isAxiosModuleSpecifier(node.moduleSpecifier)) {
      addViolation(sourceFile, node, 'UI files must not import axios; use a transaction hook.');
    }

    if (ts.isCallExpression(node)) {
      if (isGlobalFetchCall(node.expression)) {
        addViolation(sourceFile, node, 'UI files must not call fetch; use a transaction hook.');
      }

      if (isAxiosRequestCall(node.expression)) {
        addViolation(sourceFile, node, 'UI files must not call axios; use a transaction hook.');
      }

      if (
        node.expression.kind === ts.SyntaxKind.ImportKeyword &&
        node.arguments.length === 1 &&
        isAxiosModuleSpecifier(node.arguments[0])
      ) {
        addViolation(sourceFile, node, 'UI files must not dynamically import axios; use a transaction hook.');
      }

      if (
        ts.isIdentifier(node.expression) &&
        node.expression.text === 'require' &&
        node.arguments.length === 1 &&
        isAxiosModuleSpecifier(node.arguments[0])
      ) {
        addViolation(sourceFile, node, 'UI files must not require axios; use a transaction hook.');
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
}

for (const uiRoot of uiRoots) {
  for (const sourceFile of listSourceFiles(uiRoot)) {
    validateSourceFile(sourceFile);
  }
}

if (violations.length > 0) {
  console.error('UI network-boundary violations found:');
  for (const violation of violations) {
    console.error(`- ${violation.file}:${violation.line}:${violation.column} ${violation.message}`);
  }
  process.exitCode = 1;
} else {
  console.log(`Validated ${checkedFileCount} UI files: no direct axios or fetch calls found.`);
}
