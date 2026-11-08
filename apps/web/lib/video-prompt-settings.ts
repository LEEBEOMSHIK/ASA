import type { Definition, SchemaNode } from "./registry";

export const videoStyles = [
  {id:"animation_2d",name:"2D 애니메이션"},
  {id:"animation_3d",name:"3D 애니메이션"},
  {id:"live_action",name:"실사"},
] as const;

export function videoStyleField():SchemaNode {
  return {type:"string",description:"영상 스타일","x-widget":"select",enum:videoStyles.map(s=>s.id)};
}
export function isVideoStyleField(node?:SchemaNode):boolean {
  return !!node && node.type==="string" &&
    JSON.stringify(node.enum)===JSON.stringify(videoStyles.map(s=>s.id));
}

export function normalizeVideoPrompts(definition:Definition):Definition {
  const config=definition.video_prompt_modules;
  const props=definition.input_schema.properties;
  if (!props || definition.input_schema.type!=="object" ||
      !(config?.editor_managed || Object.values(props).some(node=>node["x-video-model"]))) return definition;
  const existing=props.video_style;
  const conflict=existing && !isVideoStyleField(existing);
  return {...definition,video_prompt_modules:{...config,enabled:true,editor_managed:true,
    selection_required:true,mode:"auto",profile_id:null,user_style_field:"video_style",
    confirmed_style_field:null,reference_style_field:null,metadata_style_field:null},
    input_schema:conflict?definition.input_schema:{...definition.input_schema,
      properties:{...props,video_style:{type:"string",description:"영상 스타일","x-widget":"select",
        enum:videoStyles.map(s=>s.id)}},
      required:[...new Set([...(definition.input_schema.required??[]),"video_style"])]}};
}
