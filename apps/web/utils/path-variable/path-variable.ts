export type PathVariables = Record<string, string>

const pathVariablePattern = /:(\w+)/g

export const pathVariable = (
  template: string,
  variables: PathVariables,
): string => {
  return template.replace(pathVariablePattern, (match, key: string) => {
    const value = variables[key]
    return value !== undefined ? encodeURIComponent(value) : match
  })
}
