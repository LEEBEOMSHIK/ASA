export type ArtPreset={id:string;media_type:string;label:string;description:string;image:string|null;enabled:boolean};
export type ArtCatalog={revision:number;items:ArtPreset[]};
