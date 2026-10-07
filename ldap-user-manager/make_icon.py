from PIL import Image, ImageDraw

s=256
im=Image.new("RGBA",(s,s),(11,15,20,255))
d=ImageDraw.Draw(im)
d.rounded_rectangle((18,18,238,238),radius=46,fill=(20,27,37,255),outline=(39,52,70,255),width=4)
accent=(76,141,255,255)
green=(53,196,141,255)
line=(123,151,190,255)
for p,q in [((128,80),(82,144)),((128,80),(174,144)),((82,144),(82,190)),((174,144),(174,190))]:
    d.line((p,q),fill=line,width=10)
for x,y,r,c in [(128,72,27,accent),(82,145,24,green),(174,145,24,accent),(82,198,19,accent),(174,198,19,green)]:
    d.ellipse((x-r,y-r,x+r,y+r),fill=c)
    d.ellipse((x-5,y-5,x+5,y+5),fill=(255,255,255,235))
im.save("ldap-user-manager/app.ico",sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
