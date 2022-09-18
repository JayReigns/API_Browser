
bl_info = {
    "name": "API Browser",
    "author": "JayReigns",
    "version": (1, 2, 2),
    "blender": (2, 81, 0),
    "location": "Text Editor > ToolBar > API Browser",
    "description": "Browse through the python api via the user interface",
    "category": "Development"
}

DEFAULT_MODULE = 'bpy'

ICONS = ["TRIA_DOWN", "TRIA_DOWN", "PACKAGE", "WORDWRAP_ON", "DOT", "QUESTION", "SCRIPT", "INFO", "ERROR"]
LABELS = ["Items", "Values", "Modules", "Types", "Properties", "Structs and Functions", "Methods and Functions", "Attributes", "Inaccessible"]


import bpy
try: # if bpy.app.version < (3, 3, 0):
    from console.complete_import import get_root_modules
except: #else:
    from bl_console_utils.autocomplete.complete_import import get_root_modules



def resolve_module(path):
    try:
        module = path.split('.', 1)[0]
        return eval(path, {module: __import__(module)})
    except:
        return None

def resolve_path(cur_path, info):

    def parent(path):
        """Returns the parent path"""
        return path.rpartition('[' if path.endswith(']') else '.')[0]

    type, value = ( int(i) for i in info.split() )
        
    if type == -1:
        cur_path = parent(cur_path)
    elif type == -2:
        cur_path = DEFAULT_MODULE
    elif type == 0: # index
        cur_path += f"['{API_Manager.filtered_tree[type][value]}']"
    elif type == 1: # key
        cur_path += f"[{value}]"
    else:
        if cur_path:
            cur_path += '.'
        cur_path += API_Manager.filtered_tree[type][value]

    return cur_path


class API_Manager:

    # used internally
    _data_tree       = None

    # used to check for changes
    _current_path    = None
    _current_filter  = None
    _filter_internal = None

    # public
    filtered_tree    = None
    current_module   = None


    def update(forced=False):
        api_prop = bpy.context.window_manager.api_props

        if forced or API_Manager._current_path != api_prop.path:
            API_Manager._update_path()

        elif API_Manager._current_filter != api_prop.filter or API_Manager._filter_internal != api_prop.filter_internal:
            API_Manager._update_filter()
    

    def _update_filter():
        api_prop = bpy.context.window_manager.api_props

        tree = API_Manager._data_tree
        filter_text = api_prop.filter.lower()
        filter_internal = api_prop.filter_internal

        if filter_text and filter_internal:
            tree = [ [ mod for mod in cat if not mod.startswith('_') and filter_text in mod.lower() ] for cat in tree ]

        elif filter_internal:
            tree = [ [ mod for mod in cat if not mod.startswith('_') ] for cat in tree ]

        elif filter_text:
            tree = [ [ mod for mod in cat if filter_text in mod.lower() ] for cat in tree ]
        

        API_Manager._current_filter = filter_text
        API_Manager._filter_internal = filter_internal
        API_Manager.filtered_tree = tree
    

    def _update_path():

        def categorize_module(module):

            def isiterable(mod):
                try: return not isinstance(mod, str) and iter(mod) # (str, byte) can be passed but bpy.app gets ignored
                except: return False
            
            itm, val, mod, typ, props, struct, met, att, bug = [], [], [], [], [], [], [], [], []
            
            if isiterable(module):
                if hasattr(module, 'keys'):
                    itm = [str(k) for k in list(module.keys())]
                
                if not itm:
                    val = [str(v) for v in list(module)]
            
            for i in dir(module):
                try :
                    t = str(type(eval(f'module.{i}', {'module': module})))
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


        path = bpy.context.window_manager.api_props.path
        module = resolve_module(path)

        if path:
            tree = categorize_module(module)
        else:
            tree = [[], [], get_root_modules(), [], [], [], [], [], []]
        
        API_Manager.current_module = module
        API_Manager._current_path = path
        API_Manager._data_tree = tree
        API_Manager._update_filter()



class API_OT_GOTO_Module(bpy.types.Operator):
    """go to this Module"""
    bl_idname = "api_nav.goto_module"
    bl_label = "Go To Module"
    
    info : bpy.props.StringProperty(name='Info', default='')

    @classmethod
    def description(cls, context, properties):
        api_prop = context.window_manager.api_props
        type, value = ( int(i) for i in properties.info.split() )

        if type == -1:
            return "Go to Parent Module"
        elif type == -2:
            return "Go to 'bpy' Module"
        
        module = resolve_module(resolve_path(api_prop.path, properties.info))
        desc = str(module)
        doc = str(module.__doc__)
        if doc != 'None':
            doc = doc.rstrip()
            if doc.endswith("."): doc = doc[:-1]    # blender adds an '.' after
            desc += '\n\n' + doc
        return desc
    
    def execute(self, context):

        api_prop = context.window_manager.api_props
        api_prop.filter = ''
        api_prop.path = resolve_path(api_prop.path, self.info)
        
        return {'FINISHED'}


class API_OT_Reload(bpy.types.Operator):
    """Reloads Current module"""
    bl_idname = "api_nav.reload"
    bl_label = "Reloads Current module"
    
    def execute(self, context):
        API_Manager.update(forced=True)
        return {'FINISHED'}


class API_OT_Copy_Text(bpy.types.Operator):
    """Copy Text"""
    bl_idname = "api_nav.copy_text"
    bl_label = "Copy Text"
    
    text : bpy.props.StringProperty(name='text', default='')
    
    def execute(self, context):
        context.window_manager.clipboard = self.text
        return {'FINISHED'}


class API_OT_Info( bpy.types.Operator ):
    bl_idname = "api.info"
    bl_label = "API Info"
    bl_description = "API Info"
    
    def execute( self, context ):
        return {'CANCELLED'}
    
    def invoke( self, context, event ):
        return context.window_manager.invoke_popup( self, width = 600 )
        
    def draw( self, context ):
        path = context.window_manager.api_props.path

        current_module = API_Manager.current_module
        layout = self.layout

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

        api_prop = context.window_manager.api_props
        API_Manager.update()

        
        layout = self.layout

        col = layout.column(align=True)
        
        # path bar
        row = col.row(align=True)
        row.prop(api_prop, 'path', text='')
        row.operator(API_OT_Copy_Text.bl_idname, text="", icon="COPYDOWN", emboss=False).text = api_prop.path
        row.operator(API_OT_Reload.bl_idname, text="", icon="FILE_REFRESH")
        row.operator(API_OT_Info.bl_idname, text="", icon="INFO")
        
        # operators
        row = col.row(align=True)
        row.operator(API_OT_GOTO_Module.bl_idname, text="Parent", icon="BACK").info = '-1 0'
        row.operator(API_OT_GOTO_Module.bl_idname, text='bpy', emboss=True, icon="FILE_PARENT").info = '-2 0'
        
        # search bar
        row = layout.row(align=True)
        row.prop(api_prop, "filter", icon='VIEWZOOM', text="")
        row.prop(api_prop, "filter_internal", icon='FILTER', text="", toggle=True)
        
        data_tree = API_Manager.filtered_tree
        
        for i, category in enumerate(data_tree):
            if not category:
                continue
            
            box = layout.box()

            # category label
            row = box.row()
            row.label(text=LABELS[i], icon=ICONS[i])
            
            # items
            col = box.column(align=True)
            for j, entry in enumerate(category):
                if not (j % self.columns):
                    row = col.row(align=True)
                
                row.operator(API_OT_GOTO_Module.bl_idname, text=str(entry), emboss=True).info = f'{i} {j}'



#########################################################################################


from bpy.props import StringProperty, BoolProperty, PointerProperty

class API_Props(bpy.types.PropertyGroup):
    
    path : StringProperty(name='path', description='API path', default=DEFAULT_MODULE)
    filter : StringProperty(name='filter', description='Filter entries', default='', options={'TEXTEDIT_UPDATE'})
    filter_internal : BoolProperty(name='filter internal', description='Filters entries starting with _', default=True)
    

classes = (
    API_OT_GOTO_Module,
    API_OT_Reload,
    API_OT_Copy_Text,
    API_OT_Info,
    API_PT_Browser,
    API_Props,
)

def register():
    
    for cls in classes: bpy.utils.register_class(cls)
    bpy.types.WindowManager.api_props = PointerProperty(type=API_Props, name='API Props', description='')


def unregister():
    
    del bpy.types.WindowManager.api_props
    for cls in reversed(classes): bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
