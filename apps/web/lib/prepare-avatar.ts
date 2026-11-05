export async function prepareAvatar(file: File): Promise<string> {
  if(!["image/png","image/jpeg","image/webp"].includes(file.type))throw new Error("PNG, JPG, WebP 이미지를 선택하세요.");
  if(file.size>5*1024*1024)throw new Error("이미지는 5MB 이하로 선택하세요.");
  const url=URL.createObjectURL(file);
  try {
    const image=new Image(); image.src=url; await image.decode();
    if(image.naturalWidth*image.naturalHeight>25000000)throw new Error("이미지 크기가 너무 큽니다. 2,500만 픽셀 이하로 선택하세요.");
    const canvas=document.createElement("canvas");canvas.width=96;canvas.height=96;
    const context=canvas.getContext("2d");if(!context)throw new Error("이미지를 읽을 수 없습니다.");
    const scale=Math.min(96/image.naturalWidth,96/image.naturalHeight);
    const width=image.naturalWidth*scale,height=image.naturalHeight*scale;
    context.drawImage(image,(96-width)/2,(96-height)/2,width,height);
    const data=canvas.toDataURL("image/png");
    if(data.length>50000)throw new Error("이미지를 변환할 수 없습니다. 더 단순한 이미지를 선택하세요.");
    return data;
  } catch(error) {throw new Error(error instanceof Error && error.message.includes("세요")?error.message:"이미지를 읽을 수 없습니다. 다른 파일을 선택하세요.");}
  finally {URL.revokeObjectURL(url);}
}
