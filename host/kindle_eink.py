"""Create cached, display-sized e-ink copies; source files are never altered."""
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

STYLES=('photo','crisp','comic','original')
CONTRAST={'soft':1.0,'normal':1.18,'strong':1.5}


def convert(source,width=1200,style='photo',contrast='normal',invert=False,crop='full'):
    if style not in STYLES or contrast not in CONTRAST: raise ValueError('Unknown display style.')
    width=max(320,min(2800,int(width)))
    with Image.open(source) as opened:
        opened.seek(0)
        image=ImageOps.exif_transpose(opened).convert('RGB')
    if crop in {'left','right'}:
        middle=image.width//2;overlap=max(1,image.width//40)
        image=image.crop((0,0,middle+overlap,image.height) if crop=='left' else (middle-overlap,0,image.width,image.height))
    image.thumbnail((width,5000),Image.Resampling.LANCZOS)
    if style!='original':
        image=ImageOps.autocontrast(image.convert('L'),cutoff=.5)
        image=ImageEnhance.Contrast(image).enhance(CONTRAST[contrast])
        image=image.filter(ImageFilter.UnsharpMask(radius=.8,percent=120,threshold=3))
        if style=='photo': image=image.convert('1',dither=Image.Dither.FLOYDSTEINBERG)
        else:
            threshold=165 if style=='crisp' else 145
            image=image.point(lambda value:255 if value>=threshold else 0,mode='1')
    if invert:
        mode=image.mode
        image=ImageOps.invert(image.convert('L' if mode=='1' else 'RGB'))
        if mode=='1': image=image.convert('1',dither=Image.Dither.NONE)
    data=BytesIO();image.save(data,format='PNG')
    return data.getvalue()
