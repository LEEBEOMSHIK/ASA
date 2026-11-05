import type { SchemaNode } from "./registry";

export function conditionChoices(node?: SchemaNode): (string | number | boolean)[] {
  if (!node || !["string", "number", "integer", "boolean"].includes(node.type)) return [];
  return node.enum || (node.type === "boolean" ? [true, false] : []);
}

export function conditionValueLabel(value: string | number | boolean): string {
  return typeof value === "boolean" ? value ? "예" : "아니오" : String(value);
}

export function isInputRequired(schema: SchemaNode, key: string, values: Record<string, string>): boolean {
  if (schema.type !== "object" || schema.required?.includes(key)) return true;
  const rule = schema.properties?.[key]?.["x-required-when"];
  return !!rule && values[rule.field] !== undefined && values[rule.field] !== "" &&
    values[rule.field] === String(rule.equals);
}

export function inputConditionHint(schema: SchemaNode, key: string): string | undefined {
  const rule = schema.properties?.[key]?.["x-required-when"];
  if (!rule) return undefined;
  const source = schema.properties?.[rule.field];
  return `‘${source?.description || rule.field}’에서 ‘${conditionValueLabel(rule.equals)}’ 선택 시 필수입니다.`;
}
