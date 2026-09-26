"""Geometry-faithful studio renders of the OpenSCAD exports (VTK + Pillow).
Run export.sh then checks/export_render_meshes.py first. No generative image assets.
"""
from pathlib import Path
import math, numpy as np, vtk
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'renders'; OUT.mkdir(exist_ok=True)
SCALE=2
W,H=1800,1500

def font(n,bold=False,serif=False):
 p='/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if bold else '')+'.ttf'
 if serif: p='/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'
 return ImageFont.truetype(p,n)

def make_screen():
 im=Image.new('RGB',(480,800),(242,240,225));d=ImageDraw.Draw(im)
 ink=(29,40,38);green=(49,83,60);red=(160,44,27);yellow=(213,178,55);blue=(43,75,114)
 def txt(t,y,f,fill=ink):d.text((240,y),t,font=f,fill=fill,anchor='mt')
 txt('W E D N E S D A Y',45,font(18,True))
 txt('23',93,font(133,False,True))
 txt('S E P T E M B E R',256,font(19),red)
 d.line((54,316,426,316),fill=green,width=2)
 txt('Good morning.',347,font(34,False,True))
 # Original line-art sprig, drawn as screen content, not an enclosure feature.
 d.line([(242,594),(235,553),(242,509),(226,467)],fill=green,width=4)
 leaves=[[(237,533),(195,513),(183,478),(217,491),(240,525)],
         [(238,561),(275,543),(300,505),(269,516),(237,551)],
         [(234,505),(265,485),(274,455),(244,471),(232,497)]]
 for p in leaves:d.polygon(p,fill=green)
 for x,y in [(193,564),(208,590),(295,558)]:d.ellipse((x-8,y-8,x+8,y+8),fill=red)
 txt('A little everyday inspiration.',633,font(17))
 for i,c in enumerate([ink,(242,240,225),yellow,red,green,blue]):
  x=170+i*28;d.ellipse((x-5,702,x+5,712),fill=c,outline=ink,width=1)
 txt('COUNTERFRAME  /  01',745,font(12,True))
 p=OUT/'screen_artwork.png';im.save(p);return p

SCREEN=make_screen()
def matrix(rx=0,ty=0,tz=0,local_y=0):
 a=math.radians(rx);c,s=math.cos(a),math.sin(a)
 M=np.array([[1,0,0,0],[0,c,-s,ty],[0,s,c,tz],[0,0,0,1]],float)
 T=np.eye(4);T[1,3]=local_y
 return M@T
STAND=np.eye(4)
BODY=matrix(100,0,10,94)
CARRIER=np.eye(4);CARRIER[2,3]=2.86
REAR=matrix(180,tz=34)
COLS={'front':'e4e5de','carrier':'79918b','rear':'bdc7c0','stand':'b8c1b7',
      'pi_pcb':'235d44','hat_pcb':'245174','adapter_pcb':'245174',
      'glass':'383d3a','components':'424947','fpc':'c38b37','ffc':'d7dedd','wires':'526779','power_external':'444945'}
def rgb(h):return tuple(int(h[i:i+2],16)/255 for i in (0,2,4))
def vtkmat(A):
 m=vtk.vtkMatrix4x4()
 for i in range(4):
  for j in range(4):m.SetElement(i,j,float(A[i,j]))
 return m

def add_mesh(ren,name,M=None,alpha=1):
 p=ROOT/('stl' if name in ('front','carrier','rear','stand') else 'reference')/(name+'.stl')
 r=vtk.vtkSTLReader();r.SetFileName(str(p));r.Update()
 norms=vtk.vtkPolyDataNormals();norms.SetInputConnection(r.GetOutputPort());norms.SetFeatureAngle(45);norms.SplittingOn();norms.ConsistencyOn();norms.Update()
 mp=vtk.vtkPolyDataMapper();mp.SetInputConnection(norms.GetOutputPort())
 a=vtk.vtkActor();a.SetMapper(mp)
 if M is not None:a.SetUserMatrix(vtkmat(M))
 pr=a.GetProperty();pr.SetColor(rgb(COLS[name]));pr.SetOpacity(alpha);pr.SetInterpolationToPhong();pr.SetAmbient(.17);pr.SetDiffuse(.8);pr.SetSpecular(.13);pr.SetSpecularPower(25)
 ren.AddActor(a);return a

def add_screen(ren,M):
 p=vtk.vtkPlaneSource();p.SetOrigin(48,-80,1.69);p.SetPoint1(-48,-80,1.69);p.SetPoint2(48,80,1.69)
 mp=vtk.vtkPolyDataMapper();mp.SetInputConnection(p.GetOutputPort());a=vtk.vtkActor();a.SetMapper(mp);a.SetUserMatrix(vtkmat(M))
 r=vtk.vtkPNGReader();r.SetFileName(str(SCREEN));r.Update();t=vtk.vtkTexture();t.SetInputConnection(r.GetOutputPort());t.InterpolateOn();a.SetTexture(t)
 a.GetProperty().SetAmbient(.5);a.GetProperty().SetDiffuse(.5);a.GetProperty().SetSpecular(0);ren.AddActor(a)

def add_ground(ren,z=-.1):
 p=vtk.vtkPlaneSource();p.SetOrigin(-2000,-2000,z);p.SetPoint1(2000,-2000,z);p.SetPoint2(-2000,2000,z)
 m=vtk.vtkPolyDataMapper();m.SetInputConnection(p.GetOutputPort());a=vtk.vtkActor();a.SetMapper(m);a.GetProperty().SetColor(.952,.956,.949);a.GetProperty().SetAmbient(.3);a.GetProperty().SetDiffuse(.7);ren.AddActor(a)

def light(ren,pos,power):
 l=vtk.vtkLight();l.SetLightTypeToSceneLight();l.SetPosition(*pos);l.SetFocalPoint(0,0,90);l.SetIntensity(power);ren.AddLight(l)

def render(name,mode='assembly',camera=(-300,460,250),target=(0,-18,99),scale=128,size=(1800,1500),ground=True):
 ren=vtk.vtkRenderer();ren.SetBackground(.952,.956,.949);ren.SetAutomaticLightCreation(False)
 rw=vtk.vtkRenderWindow();rw.SetOffScreenRendering(1);rw.SetSize(*size);rw.SetMultiSamples(8);rw.AddRenderer(ren)
 if mode=='assembly':
  add_mesh(ren,'stand');add_mesh(ren,'front',BODY);add_mesh(ren,'rear',BODY@REAR);add_mesh(ren,'glass',BODY);add_screen(ren,BODY)
 elif mode=='rear_assembly':
  add_mesh(ren,'stand');add_mesh(ren,'front',BODY);add_mesh(ren,'rear',BODY@REAR)
 elif mode=='internal':
  add_mesh(ren,'stand');add_mesh(ren,'front',BODY);add_mesh(ren,'glass',BODY);add_mesh(ren,'carrier',BODY@CARRIER)
  for k in ['pi_pcb','hat_pcb','adapter_pcb','components','fpc','ffc','wires']:add_mesh(ren,k,BODY)
 elif mode=='exploded':
  add_mesh(ren,'stand')
  for k,offset in [('front',-110),('glass',-55),('carrier',10),('rear',150)]:
   T=np.eye(4);T[2,3]=offset
   if k=='carrier':T=T@CARRIER
   if k=='rear':T=T@REAR
   add_mesh(ren,k,BODY@T)
  T=np.eye(4);T[2,3]=75
  for k in ['pi_pcb','hat_pcb','adapter_pcb','components']:add_mesh(ren,k,BODY@T)
 elif mode in ['front','carrier','rear','stand']:
  add_mesh(ren,mode)
 else:raise ValueError(mode)
 if mode in ['assembly','rear_assembly','internal']:add_mesh(ren,'power_external')
 if ground:add_ground(ren)
 light(ren,(-230,400,460),.85);light(ren,(330,130,280),.5);light(ren,(-120,-330,360),.75)
 # Screen-space ambient occlusion preserves real geometry and adds contact definition.
 basic=vtk.vtkRenderStepsPass(); ssao=vtk.vtkSSAOPass();ssao.SetDelegatePass(basic);ssao.SetRadius(8);ssao.SetBias(.08);ssao.SetKernelSize(64);ssao.BlurOn();ren.SetPass(ssao)
 c=ren.GetActiveCamera();c.SetPosition(*camera);c.SetFocalPoint(*target);c.SetViewUp(0,0,1);c.ParallelProjectionOn();c.SetParallelScale(scale);ren.ResetCameraClippingRange()
 rw.Render()
 if name=='internal':
  import json
  points={'HAT':[-22,8,16],'Pi':[-15,-50,14],'Adapter':[43,17,12],
          'Bonded flex':[63,0,8],'FFC':[21,0,26.5],'USB':[10,-89,7.4],
          'SPI':[-47,-23,25]}
  anchors={}
  for k,p in points.items():
   v=BODY@np.r_[p,1];ren.SetWorldPoint(*v);ren.WorldToDisplay();v=ren.GetDisplayPoint()
   anchors[k]=[float(v[0]),float(size[1]-v[1])]
  (OUT/'internal_anchors.json').write_text(json.dumps(anchors,indent=2))
 f=vtk.vtkWindowToImageFilter();f.SetInput(rw);f.SetInputBufferTypeToRGB();f.ReadFrontBufferOff();f.Update()
 w=vtk.vtkPNGWriter();w.SetFileName(str(OUT/(name+'.png')));w.SetInputConnection(f.GetOutputPort());w.Write();rw.Finalize()
 print('rendered',name,flush=True)

if __name__=='__main__':
 import sys
 tasks=sys.argv[1:] or ['assembled','rear_view','internal','exploded','front_part','carrier_part','rear_part','stand_part','side_view']
 for task in tasks:
  if task=='assembled':render(task)
  elif task=='rear_view':render(task,'rear_assembly',camera=(280,-400,240))
  elif task=='internal':render(task,'internal',camera=(160,-410,250),target=(0,-18,100),scale=121)
  elif task=='exploded':render(task,'exploded',camera=(600,-300,260),target=(0,-38,100),scale=139,size=(2200,1300),ground=False)
  elif task=='side_view':render(task,'assembly',camera=(460,-20,110),scale=122)
  elif task=='front_part':render(task,'front',camera=(190,-250,280),target=(0,0,3),scale=110,ground=False)
  elif task=='carrier_part':render(task,'carrier',camera=(210,-260,300),target=(0,0,5),scale=110,ground=False)
  elif task=='rear_part':render(task,'rear',camera=(210,-260,300),target=(0,0,14),scale=112,ground=False)
  elif task=='stand_part':render(task,'stand',camera=(200,250,190),target=(0,-26,10),scale=87,ground=False)
