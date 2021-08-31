
bl_info = {
    "name": "API Browser",
    "author": "JayReigns",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "Text Editor > ToolBar > Text Panel",
    "description": "Browse through the python api via the user interface",
    "category": "Development"
}

import bpy
from console.complete_import import get_root_modules

DEFAULT_MODULE = 'bpy'
API_INFO = None
API_PROPS = None

ICONS = ["TRIA_DOWN", "TRIA_DOWN", "PACKAGE", "WORDWRAP_ON", "DOT", "QUESTION", "SCRIPT", "INFO", "ERROR"]
LABELS = ["Items", "Values", "Modules", "Types", "Properties", "Structs and Functions", "Methods and Functions", "Attributes", "Inaccessible"]


def isiterable(mod):
    try: return not isinstance(mod, str) and iter(mod) # (str, byte) can be passed but bpy.app gets ignored
    except: return False

def get_current_module(path):
    try:
        module = path.split('.', 1)[0]
        return None if not module else eval(path, {module: __import__(module)})
    except:
        return None

def get_data_tree():
    
    if not API_INFO.current_path:
        return [[], [], get_root_modules(), [], [], [], [], [], []]
    
    itm, val, mod, typ, props, struct, met, att, bug = [], [], [], [], [], [], [], [], []
    
    current_module = API_INFO.current_module
    
    if isiterable(current_module):
        if hasattr(current_module, 'keys'):
            itm = [str(k) for k in list(current_module.keys())]
        
        if not itm:
            val = [str(v) for v in list(current_module)]
    
    for i in dir(current_module):
        try :
            t = str(type(eval(f'module.{i}', {'module': current_module})))
        except :
            bug += [i]
            continue

        if t == "<class 'module'>":
            mod += [i]
        elif t.startswith("<class 'bpy_prop"):
            props += [i]
        elif t.startswith("<class 'bpy"):
            struct += [i]
        elif t == "<class 'builtin_function_or_method'>":
            met += [i]
        elif t == "<class 'type'>":
            typ += [i]
        else :
            att += [i]
    
    return [itm, val, mod, typ, props, struct, met, att, bug]
  

def parent(path):
    """Returns the parent path"""
    return '' if not path else path.rpartition('[' if path.endswith(']') else '.')[0]


class API_Info:
    current_path   = None
    current_filter = None
    data_tree      = None
    filtered_tree  = None
    
    filter_internal = False
    is_filtered     = False
    
    current_module  = None
    
    
    def update(self):
        
        filter = False
        
        if API_PROPS.path != self.current_path:
            self.current_path = API_PROPS.path
            self.current_module = get_current_module(self.current_path)
            self.data_tree = get_data_tree()
            filter = True
        
        if API_PROPS.filter_internal != self.filter_internal:
            self.filter_internal = API_PROPS.filter_internal
            filter = True
        
        if API_PROPS.filter != self.current_filter:
            self.current_filter = API_PROPS.filter
            filter = True
        
        if filter:
            filter_text = self.current_filter.lower()
            if filter_text and self.filter_internal:
                self.filtered_tree = [ [ mod for mod in cat if not mod.startswith('_') and filter_text in mod.lower() ] for cat in self.data_tree ]
            elif self.filter_internal:
                self.filtered_tree = [ [ mod for mod in cat if not mod.startswith('_') ] for cat in self.data_tree ]
            elif filter_text:
                self.filtered_tree = [ [ mod for mod in cat if filter_text in mod.lower() ] for cat in self.data_tree ]
            
    def get_data(self):
        return self.filtered_tree if self.filter_internal or self.current_filter else self.data_tree


class API_OT_GOTO_Module(bpy.types.Operator):
    """go to this Module"""
    bl_idname = "api_nav.goto_module"
    bl_label = "GoTo Module"
    
    info : bpy.props.StringProperty(name='Info', default='')
    
    def execute(self, context):
        
        API_PROPS.filter = ''
        
        type, value = [int(i) for i in self.info.split()]
        
        if type == -1:
            API_PROPS.path = parent(API_PROPS.path)
        elif type == -2:
            API_PROPS.path = DEFAULT_MODULE
        elif type == 0:
            API_PROPS.path += f'[\'{API_INFO.get_data()[type][value]}\']'
        elif type == 1:
            API_PROPS.path += f'[{value}]'
        else:
            if API_PROPS.path:
                API_PROPS.path += '.'
            API_PROPS.path += API_INFO.get_data()[type][value]
        
        return {'FINISHED'}

class API_OT_Copy_Text(bpy.types.Operator):
    """Copy Text"""
    bl_idname = "api_nav.copy_text"
    bl_label = "Copy Text"
    
    text : bpy.props.StringProperty(name='text', default='')
    
    def execute(self, context):
        bpy.context.window_manager.clipboard = self.text
        return {'FINISHED'}


def draw_text( text, layout ):
    for line in text.split( '\n' ):
        for l in [ line[i:i+100] for i in range(0, len(line), 100) ]:
            layout.label(text=' '*8+l)
  
def draw_section( layout, label, text='', icon='SCRIPT', newline=False ):
    box = layout.box()
    row = box.row()
    
    row.label(text=label, icon=icon)
    if not newline:
        row.label(text=text)
    row.operator(API_OT_Copy_Text.bl_idname, text="", icon="COPYDOWN", emboss=False).text = text if text else label
    if newline and text:
        draw_text(text, box.column())

class API_OT_Info( bpy.types.Operator ):
    bl_idname = "api.info"
    bl_label = "API Info"
    bl_description = "API Info"
    
    def execute( self, context ):
        return {'CANCELLED'}
    
    def invoke( self, context, event ):
        return context.window_manager.invoke_popup( self, width = 600 )
      
    def draw( self, context ):
        
        path = API_PROPS.path
        current_module = API_INFO.current_module
        
        layout = self.layout
        draw_section(layout, label=path)
        draw_section(layout, label='Type:', text=str(type(current_module)), icon="SCRIPT")
        draw_section(layout, label='Return:', text=str(current_module), icon="SCRIPT", newline=True)
        draw_section(layout, label='Doc:', text=str(current_module.__doc__), icon="INFO", newline=True)
        


class API_PT_Browser(bpy.types.Panel):
    bl_idname = 'API_PT_api_browser'
    bl_space_type = "TEXT_EDITOR"
    bl_region_type = "UI"
    bl_label = "API Browser"
    bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Text"
    
    columns = 3
    
    def draw(self, context):
        
        API_INFO.update()
        
        layout = self.layout

        col = layout.column(align=True)
        
        row = col.row(align=True)
        row.prop(API_PROPS, 'path', text='')
        row.operator(API_OT_Info.bl_idname, text="", icon="INFO")
        
        row = col.row(align=True)
        row.operator(API_OT_GOTO_Module.bl_idname, text="Parent", icon="BACK").info = '-1 0'
        row.operator(API_OT_GOTO_Module.bl_idname, text='bpy', emboss=True, icon="FILE_PARENT").info = '-2 0'
        
        row = layout.row(align=True)
        row.prop(API_PROPS, "filter", icon='VIEWZOOM', text="")
        row.prop(API_PROPS, "filter_internal", icon='FILTER', text="", toggle=True)
        
        data_tree = API_INFO.get_data()
        
        for i, category in enumerate(data_tree):
            if not category:
                continue
            
            box = layout.box()
            
            row = box.row()
            row.label(text=LABELS[i], icon=ICONS[i])
            
            col = box.column(align=True)
            
            for j, entry in enumerate(category):
                if not (j % self.columns):
                    row = col.row(align=True)
                
                row.operator(API_OT_GOTO_Module.bl_idname, text=str(entry), emboss=True).info = f'{i} {j}'



#########################################################################################


from bpy.props import StringProperty, IntProperty, BoolProperty, PointerProperty

class API_Props(bpy.types.PropertyGroup):
    
    path : StringProperty(name='path', description='API path', default=DEFAULT_MODULE)
    filter : StringProperty(name='filter', description='Filter entries', default='', options={'TEXTEDIT_UPDATE'})
    filter_internal : BoolProperty(name='filter internal', description='Filters entries starting with _', default=False)
    max_entries : IntProperty(name='Reduce to ', description='No. of max entries', default=10, min=1)
    page : IntProperty(name='Page', description='Display a Page', default=0, min=0)
    

classes = (
    API_OT_GOTO_Module,
    API_OT_Copy_Text,
    API_OT_Info,
    API_PT_Browser,
    API_Props,
)

def register():
    
    for cls in classes: bpy.utils.register_class(cls)
    bpy.types.WindowManager.api_props = PointerProperty(type=API_Props, name='API Props', description='')
    
    global API_PROPS, API_INFO
    
    API_PROPS = bpy.context.window_manager.api_props
    API_INFO = API_Info()
    
def unregister():
    
    del bpy.types.WindowManager.api_props
    for cls in reverse(classes): bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()