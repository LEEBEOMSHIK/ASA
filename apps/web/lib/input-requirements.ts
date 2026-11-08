import type { SchemaNode } from "./registry";

export function inputEntries(schema: SchemaNode): [string, SchemaNode][] {
  if (schema.type !== "object") return [["value", schema]];
  const properties = schema.properties || {};
  const keys = [...new Set([...(schema.required || []), ...Object.keys(properties)])];
  const ordered = keys.filter(key => key in properties);
  const modelIndex = ordered.findIndex(key => properties[key]["x-video-model"]);
  const styleIndex = ordered.indexOf("video_style");
  if (modelIndex >= 0 && styleIndex > modelIndex) {
    ordered.splice(styleIndex, 1);
    ordered.splice(modelIndex, 0, "video_style");
  }
  for (const key of [...ordered]) {
    const source = properties[key]["x-visible-when"]?.field;
    if (source && ordered.includes(source) && source !== key) {
      ordered.splice(ordered.indexOf(key), 1);
      ordered.splice(ordered.indexOf(source) + 1, 0, key);
    }
  }
  return ordered.map(key => [key, properties[key]]);
}

export function isInputVisible(node: SchemaNode, values: Record<string, string>): boolean {
  const rule = node["x-visible-when"];
  return !rule || values[rule.field] === String(rule.equals);
}

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
