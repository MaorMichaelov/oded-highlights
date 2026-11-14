"""Headless Blender (bpy 5.x pip module) law-office plate. Usage:
   python law_office.py out.png [width height samples]"""
import sys, math, random, time
import bpy
from mathutils import Vector

out = sys.argv[1]
W = int(sys.argv[2]) if len(sys.argv) > 2 else 1280
H = int(sys.argv[3]) if len(sys.argv) > 3 else 720
SAMPLES = int(sys.argv[4]) if len(sys.argv) > 4 else 96
random.seed(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
cy = sc.cycles
cy.device = 'CPU'
cy.samples = SAMPLES
cy.use_adaptive_sampling = True
cy.adaptive_threshold = 0.03
cy.use_denoising = True
cy.denoiser = 'OPENIMAGEDENOISE'
cy.max_bounces = 6; cy.diffuse_bounces = 3; cy.glossy_bounces = 4
cy.volume_bounces = 1; cy.volume_step_rate = 2.0; cy.volume_max_steps = 64
cy.sample_clamp_indirect = 8
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.resolution_percentage = 100
sc.render.threads = 4
sc.view_settings.exposure = -0.3
sc.view_settings.view_transform = 'AgX'     # filmic-ish tonemap (Blender 4+/5)
sc.view_settings.look = 'AgX - Medium High Contrast'
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = out

def mat(name, color=(.8,.8,.8,1), rough=.5, metal=0., emit=None, estr=0., coat=0., spec=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = color
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if coat: b.inputs['Coat Weight'].default_value = coat; b.inputs['Coat Roughness'].default_value = .05
    if emit:
        b.inputs['Emission Color'].default_value = emit
        b.inputs['Emission Strength'].default_value = estr
    return m

def box(name, loc, size, m, rot=(0,0,0), bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.active_object; o.name = name
    o.scale = (size[0]/2, size[1]/2, size[2]/2)
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        bm = o.modifiers.new('bv', 'BEVEL'); bm.width = bevel; bm.segments = 2
    o.data.materials.append(m); return o

def cyl(name, loc, r, h, m, rot=(0,0,0), verts=48, r2=None):
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(location=loc, radius=r, depth=h, vertices=verts, rotation=rot)
    else:
        bpy.ops.mesh.primitive_cone_add(location=loc, radius1=r, radius2=r2, depth=h, vertices=verts, rotation=rot)
    o = bpy.context.active_object; o.name = name
    bpy.ops.object.shade_smooth()
    o.data.materials.append(m); return o

def sphere(name, loc, r, m, scale=(1,1,1)):
    bpy.ops.mesh.primitive_uv_sphere_add(location=loc, radius=r, segments=48, ring_count=24)
    o = bpy.context.active_object; o.name = name; o.scale = scale
    bpy.ops.object.shade_smooth(); o.data.materials.append(m); return o

# ---------- materials ----------
wall   = mat('wall',  (.012,.03,.035,1), .7)                  # deep teal-green paint
trim   = mat('trim',  (.06,.04,.03,1), .4)
floor  = mat('floor', (.05,.028,.018,1), .12, coat=.6)         # polished dark wood
wood   = mat('wood',  (.16,.07,.03,1), .35, coat=.3)
shelfw = mat('shelf', (.08,.035,.015,1), .45)
brass  = mat('brass', (.9,.62,.22,1), .18, 1.0)
leather= mat('leather',(.02,.02,.025,1), .45, coat=.2)
paper  = mat('paper', (.9,.88,.8,1), .8)
glass_light = mat('bulb', (1,.8,.5,1), .5, emit=(1,.62,.3,1), estr=60)
shade  = mat('shade', (.02,.2,.12,1), .35, metal=.3)
bookcols = [(.12,.01,.015),(.012,.04,.1),(.02,.09,.04),(.12,.07,.015),(.05,.02,.08),(.1,.09,.06),(.15,.03,.02),(.01,.06,.07)]
bookm = [mat(f'book{i}', (*c,1), .55) for i,c in enumerate(bookcols)]
gold_leaf = mat('gold', (.9,.7,.25,1), .25, 1.0)

# ---------- room shell (x -4.6..4.6, y -1..9.5, z 0..3.6) ----------
box('floor',(0,4.25,-.05),(9.2,10.5,.1),floor)
box('back', (0,9.55,1.8),(9.2,.1,3.6),wall)
box('left', (-4.65,4.25,1.8),(.1,10.5,3.6),wall)
box('right',(4.65,4.25,1.8),(.1,10.5,3.6),wall)
box('ceil', (0,4.25,3.65),(9.2,10.5,.1),trim)
box('front',(0,-1.05,1.8),(9.2,.1,3.6),wall)
# wainscot panels + skirting on back/left walls
box('wain_back',(0,9.47,.55),(9.2,.06,1.1),trim); box('rail',(0,9.44,1.12),(9.2,.1,.08),trim)
box('wain_left',(-4.57,4.25,.55),(.06,10.5,1.1),trim)

# ---------- built-in bookshelf (right-hand side of back wall + right wall) ----------
def bookcase(x0, y, width, height=3.0, depth=.45, rows=6, facing=1, axis='x'):
    """axis='x': shelf spans x at fixed y, books face -y."""
    t = .04
    cx = x0 + width/2
    box('bc_back',(cx,y+depth/2 -.02,height/2),(width,.03,height),shelfw)
    for i in range(0,3):
        pass
    box('bc_l',(x0,y,height/2),(.05,depth,height),shelfw); box('bc_r',(x0+width,y,height/2),(.05,depth,height),shelfw)
    box('bc_top',(cx,y,height),(width,depth,.05),shelfw)
    rh = (height-.1)/rows
    for r in range(rows+1):
        z = .05 + r*rh
        box('bc_sh',(cx,y,z),(width,depth,t),shelfw)
        if r == rows: break
        x = x0 + .06
        while x < x0 + width - .1:
            w = random.uniform(.035,.07); h = rh*random.uniform(.62,.9)
            if random.random() < .08: x += random.uniform(.1,.25); continue   # gaps
            m = random.choice(bookm)
            lean = random.uniform(-.05,.05) if random.random()<.1 else 0
            box('book',(x+w/2,y+.02,z+t/2+h/2),(w,depth*.8,h),m,rot=(0,lean,0))
            if random.random()<.25: box('spine',(x+w/2,y-depth*.4+.02,z+t/2+h*.7),(w+.002,.004,.012),gold_leaf)
            x += w+.002
bookcase(.2, 9.0, 4.3)                      # right 55% of back wall
# right wall bookcase (rotated 90deg) -- shorter, for depth
bpy.ops.object.empty_add(location=(0,0,0))

# ---------- desk (right of centre) ----------
dx, dy = 1.9, 5.2
box('desk_top',(dx,dy,.76),(2.1,1.0,.07),wood,bevel=.01)
box('desk_body_l',(dx-.9,dy,.38),(.35,.9,.72),wood); box('desk_body_r',(dx+.9,dy,.38),(.35,.9,.72),wood)
box('desk_back',(dx,dy+.42,.38),(1.5,.05,.7),wood)
box('blotter',(dx,dy-.1,.8),(.85,.5,.012),leather)
for i,(ox,oy,rz) in enumerate([(.5,.0,.3),(.55,.04,.1)]):
    box('pad',(dx+ox,dy+oy,.80+i*.012),(.22,.3,.01),paper,rot=(0,0,rz))
# stacked law books on desk
for i,c in enumerate([0,1,3,2]):
    box('stk',(dx-.75,dy+.2,.80+.035+i*.06),(.28,.2,.055),bookm[c],rot=(0,0,random.uniform(-.2,.2)))
# chair (dark silhouette, back toward camera)
box('chair_seat',(dx,dy+.95,.5),(.6,.6,.1),leather,bevel=.03)
box('chair_back',(dx,dy+1.25,.95),(.6,.1,.9),leather,bevel=.04)
# brass scales of justice on desk
sx, sy, sz = dx+.45, dy+.15, .80
cyl('s_base',(sx,sy,sz+.02),.09,.04,brass); cyl('s_base2',(sx,sy,sz+.055),.06,.03,brass)
cyl('s_col',(sx,sy,sz+.25),.012,.4,brass)
cyl('s_beam',(sx,sy,sz+.46),.008,.46,brass,rot=(0,math.pi/2,0))
sphere('s_top',(sx,sy,sz+.47),.02,brass)
for sgn in (-1,1):
    px = sx+sgn*.23
    for a in (0,1,2):
        ang=a*2*math.pi/3
    cyl('s_chain',(px,sy,sz+.32),.002,.28,brass)
    cyl('s_pan',(px,sy,sz+.17),.085,.012,brass,r2=.07)
# gavel
cyl('g_handle',(dx-.3,dy-.25,.815),.008,.22,wood,rot=(math.pi/2,0,.25))
cyl('g_head',(dx-.27,dy-.15,.83),.03,.1,wood,rot=(0,math.pi/2,.25))
# desk lamp (banker's lamp: warm emissive)
lx, ly = dx-.35, dy+.28
cyl('l_base',(lx,ly,.80),.07,.025,brass)
cyl('l_stem',(lx,ly,.93),.008,.24,brass)
cyl('l_shade',(lx,ly,1.1),.17,.14,shade,r2=.06)
sphere('l_bulb',(lx,ly,1.04),.035,glass_light)
bpy.ops.object.light_add(type='POINT',location=(lx,ly-.05,1.02))
lamp=bpy.context.active_object; lamp.data.energy=120; lamp.data.color=(1,.62,.32); lamp.data.shadow_soft_size=.05
# monitor-less: laptop closed? skip.

# ---------- rug under desk ----------
box('rug',(dx,dy-.4,.005),(3.2,2.6,.01),mat('rug',(.2,.03,.04,1),.9))

# ---------- cabinet / globe / plant, mid-left kept sparse ----------
box('cab',(-2.9,9.1,.5),(1.4,.55,1.0),wood,bevel=.015)
sphere('globe',(-2.9,9.1,1.22),.2,mat('globe',(.05,.2,.35,1),.35,coat=.5))
cyl('globe_stand',(-2.9,9.1,1.03),.05,.06,brass)
# framed certificates (dark) on left back wall
for i in range(3):
    box('frame',(-3.6+i*.8,9.48,1.95),(.5,.03,.65),mat('fr',(.5,.35,.1,1),.3,.9))
    box('cert',(-3.6+i*.8,9.465,1.95),(.42,.01,.57),paper)

# ---------- window on left wall: cool moonlight source (dim, calm) ----------
box('win_frame',(-4.58,5.2,1.95),(.06,2.0,2.2),trim)
box('win_glass',(-4.55,5.2,1.95),(.02,1.8,2.0),mat('wg',(.4,.55,.9,1),.2,emit=(.25,.4,.9,1),estr=1.2))

# ---------- lights ----------
def area(name, loc, target, size, energy, color, shape='RECTANGLE', sy=None, spread=None):
    bpy.ops.object.light_add(type='AREA', location=loc)
    o = bpy.context.active_object; o.name = name
    o.data.energy = energy; o.data.color = color; o.data.shape = shape
    o.data.size = size
    if shape=='RECTANGLE': o.data.size_y = sy or size
    if spread: o.data.spread = math.radians(spread)
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat('-Z','Y').to_euler()
    return o
area('key_warm',(4.3,2.2,3.2),(1.9,5.2,.8),2.5,650,(1,.62,.32),sy=2.0)          # warm key from right-front-high
area('rim_cool',(-3.6,8.2,3.3),(1.2,5.0,1.0),2.0,420,(.25,.45,1.0),sy=1.5)         # cool rim from back-left
area('shelf_wash',(2.4,7.5,3.4),(2.4,9.0,1.5),3.0,120,(1,.7,.4),sy=.8)             # warm wash on books
area('fill_floor',(-1,0,3.2),(-1,5,0),3.0,10,(.35,.5,1),sy=3)                     # tiny cool fill (keeps left dark)
# window shaft: spot from the left window across the room with volumetrics
bpy.ops.object.light_add(type='SPOT',location=(-4.3,5.2,2.4))
sp=bpy.context.active_object; sp.data.energy=700; sp.data.color=(.45,.6,1); sp.data.spot_size=math.radians(38); sp.data.spot_blend=.6; sp.data.shadow_soft_size=.3
sp.rotation_euler=(Vector((2.0,5.0,.3))-Vector((-4.3,5.2,2.4))).to_track_quat('-Z','Y').to_euler()

# ---------- volumetric haze (cube domain) ----------
bpy.ops.mesh.primitive_cube_add(location=(0,4.25,1.8)); v=bpy.context.active_object; v.scale=(4.55,5.2,1.78); v.name='haze'
vm=bpy.data.materials.new('haze'); vm.use_nodes=True; nt=vm.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
vs=nt.nodes.new('ShaderNodeVolumeScatter'); vs.inputs['Density'].default_value=.011; vs.inputs['Anisotropy'].default_value=.55
vo=nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(vs.outputs[0],vo.inputs['Volume'])
v.data.materials.append(vm); v.display_type='WIRE'

# ---------- world: very dark ----------
w=bpy.data.worlds.new('w'); sc.world=w; w.use_nodes=True
w.node_tree.nodes['Background'].inputs['Color'].default_value=(.01,.012,.02,1)

# ---------- camera with DOF, left 45% kept calm by composition ----------
bpy.ops.object.empty_add(location=(dx,dy,.9)); foc=bpy.context.active_object
bpy.ops.object.camera_add(location=(.3,-.6,1.25)); cam=bpy.context.active_object
cam.data.lens=40; cam.data.sensor_width=36
cam.rotation_euler=(Vector((.6,5,1.2))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.dof.use_dof=True; cam.data.dof.focus_object=foc; cam.data.dof.aperture_fstop=1.6
sc.camera=cam

t=time.time(); bpy.ops.render.render(write_still=True)
print(f'RENDER_SECONDS {time.time()-t:.1f}')
