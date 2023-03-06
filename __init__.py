
bl_info = {
    "name": "API Browser",
    "author": "JayReigns",
    "version": (1, 3, 1),
    "blender": (2, 80, 0),
    "location": "Text Editor > ToolBar > API Browser",
    "description": "Browse through the python api via the user interface",
    "category": "Development"
}

import bpy
from bpy.props import IntProperty, StringProperty, BoolProperty, PointerProperty
from bpy.types import Operator, Menu, Panel, PropertyGroup, AddonPreferences

try:  # if bpy.app.version < (3, 3, 0):
    from console.complete_import import get_root_modules
except:  # else:
    from bl_console_utils.autocomplete.complete_import import get_root_modules


# category icons
ICONS = ["TRIA_DOWN", "TRIA_DOWN", "PACKAGE", "WORDWRAP_ON",
         "DOT", "QUESTION", "SCRIPT", "INFO", "ERROR"]

# category labels
LABELS = ["Items", "Values", "Modules", "Types", "Properties",
          "Structs and Functions", "Methods and Functions", "Attributes", "Inaccessible"]

ENABLED = [True] * len(LABELS)

GOTO_PARENT = -1
GOTO_DEFAULT = -2
GOTO_HISTORY = -3

def get_preferences(context):
    return context.preferences.addons[__name__].preferences

def resolve_module(path):
    """Returns Python Object from String Path"""
    try:
        module = path.split('.', 1)[0]
        return eval(path, {module: __import__(module)})
    except:
        return None


def parent(path):
    """Returns the parent path"""
    return path.rpartition('[' if path.endswith(']') else '.')[0]


def resolve_path(cur_path, info, default=""):
    """Returns tuple(path, filter, enabled[])"""

    filter = ""
    enabled = [True] * len(LABELS)
    type, value = (int(i) for i in info.split())

    if type >= 0:
        if   type == 0: # key
            cur_path += f"['{API_Manager.get_data_tree()[type][value]}']"

        elif type == 1: # index
            cur_path += f"[{value}]"

        else:
            if cur_path:
                cur_path += '.'
            cur_path += API_Manager.get_data_tree()[type][value]
    
    elif type == GOTO_PARENT:
        cur_path = parent(cur_path)

    elif type == GOTO_DEFAULT:
        cur_path = default

    elif type == GOTO_HISTORY:
        hist = API_Manager.get_history()[value]
        cur_path, filter, enabled = hist
    
    return cur_path, filter, enabled


def get_module_description(path):
    module = resolve_module(path)
    desc = str(module)
    doc = str(module.__doc__)

    if doc != "None":
        # omit last '.'; blender adds an '.' after
        doc = doc.rstrip()
        if doc.endswith("."):
            doc = doc[:-1]    
        desc += "\n\n" + doc
    
    return desc

class API_Manager:

    # used to check for changes
    _current_path = None
    _current_filter = None
    _filter_internal = None

    # used internally
    _data_tree = None
    _filtered_tree = None
    _current_module = None
    _history = []

    def get_current_path():
        return API_Manager._current_path
    
    def get_current_module():
        return API_Manager._current_module
    
    def get_history():
        return API_Manager._history
    
    def get_data_tree():
        return API_Manager._filtered_tree

    def check_for_update():
        api_prop = bpy.context.window_manager.api_props

        if API_Manager._current_path != api_prop.path:
            API_Manager.update_path()

        elif API_Manager._current_filter != api_prop.filter or API_Manager._filter_internal != api_prop.filter_internal:
            API_Manager._update_filter()

    def _update_filter():
        api_prop = bpy.context.window_manager.api_props

        tree = API_Manager._data_tree
        filter_text = api_prop.filter.lower()
        filter_internal = api_prop.filter_internal

        if filter_text and filter_internal:
            tree = [[mod for mod in cat if not mod.startswith('_') and filter_text in mod.lower()] for cat in tree]

        elif filter_internal:
            tree = [[mod for mod in cat if not mod.startswith('_')] for cat in tree]

        elif filter_text:
            tree = [[mod for mod in cat if filter_text in mod.lower()] for cat in tree]

        API_Manager._current_filter = filter_text
        API_Manager._filter_internal = filter_internal
        API_Manager._filtered_tree = tree


    def _update_history(new_path):

        def remove_if_exists(hist, exclude):
            return [(p,*d) for p, *d in hist if p not in exclude]

        old_path = API_Manager._current_path
        filter = API_Manager._current_filter

        # remove new_path and old_path if exists
        API_Manager._history = remove_if_exists(API_Manager._history, (new_path, old_path))
        
        if not old_path:
            return
        
        history = API_Manager._history
        history_size = get_preferences(bpy.context).history_size

        # append old_path
        history.append((old_path, filter, ENABLED[:]))

        if len(history) > history_size:
            additional = len(history) - history_size
            del history[:additional]


    def update_path():

        path = bpy.context.window_manager.api_props.path
        module = resolve_module(path)

        if path:
            tree = API_Manager.categorize_module(module)
        else:
            tree = [[], [], get_root_modules(), [], [], [], [], [], []]

        API_Manager._update_history(path)

        API_Manager._current_module = module
        API_Manager._current_path = path
        API_Manager._data_tree = tree

        API_Manager._update_filter()

    
    def categorize_module(module):

        def isiterable(mod):
            try:
                # (str, byte) can be passed but bpy.app gets ignored
                return not isinstance(mod, str) and iter(mod)
            except:
                return False

        itm, val, mod, typ, props, struct, met, att, bug = [], [], [], [], [], [], [], [], []

        if isiterable(module):
            if hasattr(module, 'keys'):
                itm = [str(k) for k in list(module.keys())]

            if not itm:
                val = [str(v) for v in list(module)]

        for i in dir(module):
            try:
                t = str(type(eval(f"module.{i}", {'module': module})))
            except:
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
            else:
                att += [i]

        return [itm, val, mod, typ, props, struct, met, att, bug]

#########################################################################################
# OPERATORS, MENUS
#########################################################################################


class API_MT_History_Menu(Menu):
    bl_label = "History"
    bl_idname = "API_MT_History_Menu"

    def draw(self, context):
        layout = self.layout
        length = len(API_Manager.get_history()) - 1
        for i, item in enumerate(reversed(API_Manager.get_history())):
            layout.operator(API_OT_GOTO_Module.bl_idname, 
                            text=item[0]).info = f'{GOTO_HISTORY} {length - i}'


class API_OT_History(Operator):
    """Show History"""
    bl_label = "History"
    bl_idname = "api_browser.history"

    def execute(self, context):
        bpy.ops.wm.call_menu(name=API_MT_History_Menu.bl_idname)
        return {'FINISHED'}


class API_OT_EnableDisable(Operator):
    """Enable/Disable Category"""
    bl_label = "Enable/Disable"
    bl_idname = "api_browser.enable_disable"

    index: IntProperty(name="index", default=-1)

    def execute(self, context):
        global ENABLED
        ENABLED[self.index] = not ENABLED[self.index]
        return {'FINISHED'}


class API_OT_GOTO_Module(Operator):
    """Go to this Module"""
    bl_idname = "api_browser.goto_module"
    bl_label = "Go To Module"

    # category_index, item_index; ex: "1 2"
    info: StringProperty(name="info", default="")


    @classmethod
    def description(cls, context, properties):
        # provides live description
        prefs = get_preferences(context)
        api_prop = context.window_manager.api_props

        path, *_ = resolve_path(api_prop.path, properties.info, default=prefs.default_module)

        if path:
            return get_module_description(path)
        

    def execute(self, context):
        global ENABLED, LABELS

        prefs = get_preferences(context)
        api_prop = context.window_manager.api_props

        path, filter, enabled = resolve_path(api_prop.path, self.info, default=prefs.default_module)

        api_prop.path = path
        api_prop.filter = filter
        API_Manager.update_path()

        ENABLED = enabled
        
        return {'FINISHED'}


class API_OT_Reload_Module(Operator):
    """Reloads the Current module"""
    bl_idname = "api_browser.reload"
    bl_label = "Reload"

    def execute(self, context):
        API_Manager.update_path()
        self.report({"INFO"}, "Module Reloaded!")
        return {'FINISHED'}


class API_OT_Copy_Text(Operator):
    """Copy Text"""
    bl_idname = "api_browser.copy_text"
    bl_label = "Copy"

    text: bpy.props.StringProperty(name="text", default="")

    def execute(self, context):
        context.window_manager.clipboard = self.text
        self.report({"INFO"}, "Path Copied!")
        return {'FINISHED'}


class API_OT_Module_Info(Operator):
    """Show Module Info"""
    bl_idname = "api_browser.module_info"
    bl_label = "Info"

    def execute(self, context):
        return {'CANCELLED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=600)

    def draw(self, context):
        path = context.window_manager.api_props.path

        current_module = API_Manager.get_current_module()
        layout = self.layout

        def draw_text(text, layout):
            for line in text.split('\n'):
                for l in [line[i:i+100] for i in range(0, len(line), 100)]:
                    layout.label(text=" "*8+l)

        def draw_section(layout, label, text="", icon="SCRIPT", newline=False):
            box = layout.box()
            row = box.row()

            row.label(text=label, icon=icon)
            if not newline:
                row.label(text=text)
            row.operator(API_OT_Copy_Text.bl_idname, text="", icon="COPYDOWN", emboss=False).text = text if text else label
            if newline and text:
                draw_text(text, box.column())

        draw_section(layout, label=path)
        draw_section(layout, label="Type:", text=str(type(current_module)), icon="SCRIPT")
        draw_section(layout, label="Return:", text=str(current_module), icon="SCRIPT", newline=True)
        draw_section(layout, label="Doc:", text=str(current_module.__doc__), icon="INFO", newline=True)

#########################################################################################
# PANELS
#########################################################################################

class API_PT_Browser(Panel):
    bl_idname = "API_PT_Browser"
    bl_space_type = "TEXT_EDITOR"
    bl_region_type = "UI"
    bl_label = "API Browser"
    bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Text"

    def draw(self, context):

        API_Manager.check_for_update()

        prefs = get_preferences(context)
        api_prop = context.window_manager.api_props

        layout = self.layout
        col = layout.column(align=True)

        # path bar
        row = col.row(align=True)
        row.prop(api_prop, 'path', text='')
        row.operator(API_OT_Copy_Text.bl_idname, text="",
                     icon="COPYDOWN", emboss=False).text = api_prop.path
        row.operator(API_OT_Reload_Module.bl_idname, text="", icon="FILE_REFRESH")
        row.operator(API_OT_Module_Info.bl_idname, text="", icon="INFO")

        # operators
        row = col.row(align=True)
        row.operator(API_OT_GOTO_Module.bl_idname,
                     text="Parent", icon="BACK").info = f'{GOTO_PARENT} 0'
        row.operator(API_OT_GOTO_Module.bl_idname, text=prefs.default_module,
                     emboss=True, icon="FILE_PARENT").info = f'{GOTO_DEFAULT} 0'

        # history
        row.operator(API_OT_History.bl_idname, text="", icon="RECOVER_LAST")

        # search bar
        row = layout.row(align=True)
        row.prop(api_prop, "filter", icon='VIEWZOOM', text="")
        row.prop(api_prop, "filter_internal",
                 icon='FILTER', text="", toggle=True)

        data_tree = API_Manager.get_data_tree()
        columns = prefs.columns

        for i, category in enumerate(data_tree):
            if not category:
                continue

            box = layout.box()
            enabled = ENABLED[i]

            # category label
            row = box.row()
            icon = "CHECKBOX_HLT" if enabled else "CHECKBOX_DEHLT"
            row.operator(API_OT_EnableDisable.bl_idname, text="", icon=icon).index = i
            row.label(text=f"{LABELS[i]} ({len(category)})", icon=ICONS[i])

            if enabled:
                # items
                col = box.column(align=True)
                for j, entry in enumerate(category):
                    if not (j % columns):
                        row = col.row(align=True)

                    row.operator(API_OT_GOTO_Module.bl_idname, text=str(entry),
                                emboss=True).info = f'{i} {j}'
    
        return


class APIBrowserAddonPreferences(AddonPreferences):
    bl_idname = __name__

    default_module: StringProperty(
        name="Default Module",
        description="Default module to display",
        default="bpy",
    )
    columns: IntProperty(
        name="Column Count",
        description="Column count",
        default=3,
    )
    history_size: IntProperty(
        name="History Size",
        description="Number of history items to keep",
        default=10,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        col = layout.column(align=True)
        col.prop(self, "default_module")
        col.prop(self, "columns")
        col.prop(self, "history_size")


#########################################################################################
# PROPERTIES
#########################################################################################

class API_Props(PropertyGroup):

    path: StringProperty(
        name="Path",
        description="API path",
        default="bpy"
    )
    filter: StringProperty(
        name="Filter",
        description="Filters matching entries",
        default="",
        options={'TEXTEDIT_UPDATE'}
    )
    filter_internal: BoolProperty(
        name="Filter Internal",
        description="Filters entries starting with '_'",
        default=True
    )


classes = (
    API_MT_History_Menu,
    API_OT_History,
    API_OT_EnableDisable,
    API_OT_GOTO_Module,
    API_OT_Reload_Module,
    API_OT_Copy_Text,
    API_OT_Module_Info,
    API_PT_Browser,
    APIBrowserAddonPreferences,
    API_Props,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.WindowManager.api_props = PointerProperty(
        type=API_Props,
        name="API Props",
        description=""
    )


def unregister():

    del bpy.types.WindowManager.api_props

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
