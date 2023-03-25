
bl_info = {
    "name": "API Browser",
    "author": "JayReigns",
    "version": (2, 0, 0),
    "blender": (2, 80, 0),
    "location": "Text Editor > ToolBar > API Browser",
    "description": "Browse through the python api via the user interface",
    "category": "Development"
}

import bpy
from bpy.types import Operator, Menu, Panel, PropertyGroup, AddonPreferences
from bpy.props import IntProperty, StringProperty, BoolProperty, PointerProperty, CollectionProperty

try:  # if bpy.app.version < (3, 3, 0):
    from console.complete_import import get_root_modules
except ImportError:  # else:
    from bl_console_utils.autocomplete.complete_import import get_root_modules


# labels, icons
CATEGORIES = (
    ('Items', 'TRIA_DOWN'),
    ('Values', 'TRIA_DOWN'),
    ('Modules', 'PACKAGE'),
    ('Types', 'WORDWRAP_ON'),
    ('Properties', 'DOT'),
    ('Structs and Functions', 'QUESTION'),
    ('Methods and Functions', 'SCRIPT'),
    ('Attributes', 'INFO'),
    ('Inaccessible', 'ERROR'),
)


EXCEPTIONS = None


def get_preferences():
    try:
        return bpy.context.preferences.addons[__name__].preferences
    except:
        # Used when running inside TextEditor
        class Dummy:
            default_module = 'bpy'
            columns = 3
            history_size = 10
        return Dummy


def resolve_module(path):
    """Returns Python Object from String Path"""
    try:
        module = path.split('.', 1)[0]
        return eval(path, {module: __import__(module)})
    except:
        return None


def parent(path):
    """Returns the parent path"""
    return path.rpartition('[' if path.endswith(']') else '.')[0]   # rsplit() not used


def resolve_path(path, info):
    """Returns Submodule path from info=(cat, idx) tuple"""

    data_tree = API_Manager.get_data_tree()
    
    cat, idx = (int(i) for i in info.split())

    if cat == 0:  # key
        path += f"['{data_tree[cat][idx]}']"

    elif cat == 1:  # index
        path += f"[{idx}]"

    else:
        if path:
            path += '.'
        path += data_tree[cat][idx]

    return path


def get_module_description(path):
    module = resolve_module(path)
    desc = str(module)
    doc = str(module.__doc__).rstrip()

    if doc != "None":
        # omit last '.'; blender adds an '.' after
        desc += "\n\n" + doc[:-1] if doc.endswith(".") else doc

    return desc


def categorize_module(path):

    def isiterable(mod):
        try:
            # (str, byte) can be passed but bpy.app gets ignored
            return iter(mod) and not isinstance(mod, str)
        except:
            return False

    if not path:
        return [[], [], get_root_modules(), [], [], [], [], [], []]

    itm, val, mod, typ, props, struct, met, att, bug = [], [], [], [], [], [], [], [], []

    module = resolve_module(path)

    if isiterable(module):
        if hasattr(module, 'keys'):
            itm = [str(k) for k in module.keys()]
        else:
            val = [str(v) for v in module]

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


class API_Manager:

    # used to check for changes
    _current_path = None
    _current_filter = None
    _filter_internal = None

    # used internally
    _data_tree = None
    _filtered_tree = None

    def get_data_tree():
        return API_Manager._filtered_tree
    
    def update():
        api_props = bpy.context.window_manager.api_props

        if api_props.path != API_Manager._current_path:
            API_Manager.update_path()

        elif api_props.filter != API_Manager._current_filter \
                or api_props.filter_internal != API_Manager._filter_internal:
            API_Manager.update_filter()


    def update_filter():

        api_props = bpy.context.window_manager.api_props

        filter_text = api_props.filter.lower()
        filter_internal = api_props.filter_internal
        tree = API_Manager._data_tree

        if filter_text and filter_internal:
            tree = [[mod for mod in cat if not mod.startswith('_') and filter_text in mod.lower()]
                    for cat in tree]

        elif filter_internal:
            tree = [[mod for mod in cat if not mod.startswith('_')]
                    for cat in tree]

        elif filter_text:
            tree = [[mod for mod in cat if filter_text in mod.lower()]
                    for cat in tree]

        API_Manager._current_filter = api_props.filter
        API_Manager._filter_internal = api_props.filter_internal
        API_Manager._filtered_tree = tree


    def update_history(new_path, old_path):

        # in case of reload don't change history
        if new_path == old_path:
            return
        
        prefs = get_preferences()
        api_props = bpy.context.window_manager.api_props
        history = api_props.history

        if old_path:    # don't push empty path
            # push to history
            hist = history.add()
            hist.name = old_path
            hist.path = old_path
            hist.category_enable_flag = api_props.category_enable_flag
            hist.filter = api_props.filter
            # hist.filter_internal = api_props.filter_internal

        # reset props
        api_props.category_enable_flag = 0xFFFF
        api_props.filter = ""

        if new_path:
            # check if exists in history
            idx = history.find(new_path)
            if idx != -1:
                # copy props from history
                hist = history[idx]
                api_props.category_enable_flag = hist.category_enable_flag
                api_props.filter = hist.filter
                # api_props.filter_internal = hist.filter_internal

                # remove
                history.remove(idx)

        # remove extras
        hist_limit = prefs.history_size
        for i in range(0, len(history) - hist_limit):
            history.remove(i)
    

    def update_path():

        api_props = bpy.context.window_manager.api_props
        new_path = api_props.path
        old_path = API_Manager._current_path

        API_Manager._data_tree = categorize_module(new_path)
        API_Manager.update_history(new_path, old_path)
        API_Manager._current_path = new_path

        API_Manager.update_filter()


#########################################################################################
# OPERATORS, MENUS
#########################################################################################


class API_OT_History_Clear(Operator):
    """Clears History"""
    bl_idname = "api_browser.history_clear"
    bl_label = "Clear History"

    def execute(self, context):

        api_props = context.window_manager.api_props
        api_props.history.clear()

        self.report({"INFO"}, "History Cleared!")
        return {'FINISHED'}

class API_MT_History_Menu(Menu):
    bl_label = "History"
    bl_idname = "API_MT_History_Menu"

    def draw(self, context):
        
        api_props = context.window_manager.api_props
        history = api_props.history
        layout = self.layout

        layout.operator(API_OT_History_Clear.bl_idname, text="Clear", icon="CANCEL")
        for i in range(len(history) - 1, -1, -1):
            item = history[i]
            layout.operator(API_OT_History.bl_idname, text=item.path).index = i


class API_OT_History(Operator, Menu):
    """Show History"""
    bl_label = "History"
    bl_idname = "api_browser.history"

    index: IntProperty(name="index", default=-1)

    @classmethod
    def description(cls, context, properties):

        api_props = context.window_manager.api_props
        idx = properties.index

        if idx == -1:
            return
        
        path = api_props.history[idx].path

        if path:
            return get_module_description(path)

    @classmethod
    def poll(cls, context):
        return len(context.window_manager.api_props.history) > 0

    def execute(self, context):

        api_props = context.window_manager.api_props
        idx = self.index

        if idx == -1:
            bpy.ops.wm.call_menu(name=API_MT_History_Menu.bl_idname)
            return {'FINISHED'}

        hist = api_props.history[idx]
        api_props.path = hist.path
        self.index = -1

        return {'FINISHED'}


class API_OT_EnableDisable(Operator):
    """Enable/Disable Category"""
    bl_label = "Enable/Disable"
    bl_idname = "api_browser.enable_disable"

    index: IntProperty(name="index", default=-1)

    def execute(self, context):

        api_props = context.window_manager.api_props
        c_flag = api_props.category_enable_flag
        c_mask = 0x1 << self.index
        api_props.category_enable_flag = c_flag ^ c_mask

        return {'FINISHED'}


class API_OT_GOTO_Parent(Operator):
    """Go to parent Module"""
    bl_idname = "api_browser.goto_parent_module"
    bl_label = "Parent"

    @classmethod
    def poll(cls, context):
        return True if context.window_manager.api_props.path else False

    @classmethod
    def description(cls, context, properties):
        api_props = context.window_manager.api_props
        path = parent(api_props.path)

        if path:
            return get_module_description(path)

    def execute(self, context):

        api_props = context.window_manager.api_props
        api_props.path = parent(api_props.path)

        return {'FINISHED'}


class API_OT_GOTO_Default(Operator):
    """Go to Default Module"""
    bl_idname = "api_browser.goto_default_module"
    bl_label = "Default"

    @classmethod
    def description(cls, context, properties):
        prefs = get_preferences()
        path = prefs.default_module

        if path:
            return get_module_description(path)

    def execute(self, context):

        prefs = get_preferences()
        api_props = context.window_manager.api_props
        api_props.path = prefs.default_module

        return {'FINISHED'}


class API_OT_GOTO_Sub_Module(Operator):
    """Go to Sub Module"""
    bl_idname = "api_browser.goto_sub_module"
    bl_label = "Go To Module"

    # category_index, item_index; ex: "1 2"
    info: StringProperty(name="info", default="")

    @classmethod
    def description(cls, context, properties):
        api_props = context.window_manager.api_props
        path = resolve_path(api_props.path, properties.info)

        if path:
            return get_module_description(path)

    def execute(self, context):

        api_props = context.window_manager.api_props
        api_props.path = resolve_path(api_props.path, self.info)

        return {'FINISHED'}


class API_OT_Reload_Module(Operator):
    """Reloads the Current module"""
    bl_idname = "api_browser.reload"
    bl_label = "Reload"

    def execute(self, context):

        # api_props = context.window_manager.api_props
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

    module = None

    @classmethod
    def poll(cls, context):
        return True if context.window_manager.api_props.path else False

    def execute(self, context):
        return {'CANCELLED'}

    def invoke(self, context, event):
        path = context.window_manager.api_props.path
        self.module = resolve_module(path)
        return context.window_manager.invoke_popup(self, width=600)

    def draw(self, context):
        path = context.window_manager.api_props.path
        current_module = self.module
        layout = self.layout

        def draw_text(text, layout):
            for line in text.split('\n'):
                for l in (line[i:i+100] for i in range(0, len(line), 100)):
                    layout.label(text=" "*8+l)

        def draw_section(layout, label, text="", icon="SCRIPT"):
            box = layout.box()
            row = box.row()

            row.label(text=label, icon=icon)
            row.operator(API_OT_Copy_Text.bl_idname, text="",
                         icon="COPYDOWN", emboss=False).text = text if text else label
            if text:
                draw_text(text, box.column())

        draw_section(layout, path)
        draw_section(layout, "Type:",   str(type(current_module)))
        draw_section(layout, "Return:", str(current_module))
        draw_section(layout, "Doc:",    str(current_module.__doc__), icon="INFO")

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

        API_Manager.update()

        prefs = get_preferences()
        api_props = context.window_manager.api_props

        data_tree = API_Manager.get_data_tree()
        columns = prefs.columns
        c_flag = api_props.category_enable_flag

        layout = self.layout
        col = layout.column(align=True)

        # path bar
        row = col.row(align=True)
        row.prop(api_props, 'path', text='')
        row.operator(API_OT_Copy_Text.bl_idname, text="",
                     icon="COPYDOWN", emboss=False).text = api_props.path
        row.operator(API_OT_Reload_Module.bl_idname,
                     text="", icon="FILE_REFRESH")
        row.operator(API_OT_Module_Info.bl_idname, text="", icon="INFO")

        # navigation bar
        row = col.row(align=True)
        row.operator(API_OT_GOTO_Parent.bl_idname, text="Parent", icon="BACK")
        row.operator(API_OT_GOTO_Default.bl_idname, text=prefs.default_module,
                     emboss=True, icon="FILE_PARENT")

        # history
        # row = row.row(align=True)
        row.operator(API_OT_History.bl_idname, text="", icon="RECOVER_LAST")

        # search bar
        row = layout.row(align=True)
        row.prop(api_props, "filter", icon='VIEWZOOM', text="")
        row.prop(api_props, "filter_internal",
                 icon='FILTER', text="", toggle=True)

        for i, category in enumerate(data_tree):
            if not category:
                continue

            box = layout.box()
            c_label, c_icon = CATEGORIES[i]
            c_enabled = c_flag & (0x1 << i)

            # category label
            row = box.row()
            chk = "CHECKBOX_HLT" if c_enabled else "CHECKBOX_DEHLT"
            row.operator(API_OT_EnableDisable.bl_idname,
                         text="", icon=chk).index = i
            row.label(text=f"{c_label} ({len(category)})", icon=c_icon)

            if c_enabled:
                # items
                col = box.column(align=True)
                for j, entry in enumerate(category):
                    if not (j % columns):
                        row = col.row(align=True)

                    row.operator(API_OT_GOTO_Sub_Module.bl_idname, text=str(entry),
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

class API_History_Props(PropertyGroup):

    path: StringProperty(
        name="Path",
        description="API path",
        default="bpy",
    )
    category_enable_flag: IntProperty(
        name="Category Enable Flag",
        description="Category Enable/Disable Flag",
        default=0xFFFF,
    )
    filter: StringProperty(
        name="Filter",
        description="Filters matching entries",
        default="",
        options={'TEXTEDIT_UPDATE'},
    )

# API_Props can extend API_History_Props
# to save redundancy
# but does not work in blender 2.80
class API_Props(PropertyGroup):

    path: StringProperty(
        name="Path",
        description="API path",
        default="bpy",
    )
    category_enable_flag: IntProperty(
        name="Category Enable Flag",
        description="Category Enable/Disable Flag",
        default=0xFFFF,
    )
    filter: StringProperty(
        name="Filter",
        description="Filters matching entries",
        default="",
        options={'TEXTEDIT_UPDATE'},
    )
    filter_internal: BoolProperty(
        name="Filter Internal",
        description="Filters entries starting with '_'",
        default=True,
    )
    history: CollectionProperty(
        type=API_History_Props,
        name="API History Props",
        description=""
    )


classes = (
    API_MT_History_Menu,
    API_OT_History_Clear,
    API_OT_History,
    API_OT_EnableDisable,
    API_OT_GOTO_Parent,
    API_OT_GOTO_Default,
    API_OT_GOTO_Sub_Module,
    API_OT_Reload_Module,
    API_OT_Copy_Text,
    API_OT_Module_Info,
    API_PT_Browser,
    APIBrowserAddonPreferences,
    API_History_Props,
    API_Props,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.api_props = PointerProperty(
        type=API_Props,
        name="API Props",
        description="",
    )


def unregister():

    del bpy.types.WindowManager.api_props

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
