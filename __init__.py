
bl_info = {
    "name": "API Browser",
    "author": "JayReigns",
    "version": (3, 1, 0),
    "blender": (2, 80, 0),
    "location": "Text Editor > ToolBar > API Browser",
    "description": "Browse through the python api via the user interface",
    "category": "Development"
}

import re, builtins
import bpy
from bpy.types import Operator, Menu, Panel, PropertyGroup, AddonPreferences
from bpy.props import IntProperty, StringProperty, BoolProperty,\
    PointerProperty, CollectionProperty, BoolVectorProperty, IntVectorProperty

try:  # if bpy.app.version < (3, 3, 0):
    from console.complete_import import get_root_modules
except ImportError:  # else:
    from bl_console_utils.autocomplete.complete_import import get_root_modules


# labels, icons(unused)
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

_DATA_TREE = None

def get_props():
    return bpy.context.window_manager.api_props


def get_preferences():
    try:
        return bpy.context.preferences.addons[__name__].preferences
    except:
        # Used when running inside Blender TextEditor
        class DummyPreference:
            default_module = 'bpy'
            columns = 3
            rows = 10
            history_size = 10
            restore_history_settings = True
            auto_reload = True
        return DummyPreference


def get_data_tree(update=False, reload=False):
    global _DATA_TREE
    api_props = get_props()
    prefs = get_preferences()

    if _DATA_TREE == None or reload:
       _DATA_TREE = categorize_module(api_props.path)
    
    elif update:
        new_path = api_props.path
        old_path = api_props.old_path
        
        if prefs.auto_reload or new_path != old_path:
            _DATA_TREE = categorize_module(new_path)
            update_history(new_path, old_path)
            api_props.old_path = new_path
    
    filtered = filter_tree(_DATA_TREE)
    return filtered


def filter_tree(tree):

    api_props = get_props()

    filter_text = api_props.filter.lower()
    filter_internal = api_props.filter_internal

    tree = ([(idx, mod) for idx, mod in enumerate(cat)] for cat in tree)

    if filter_internal:
        tree = ([(idx, mod) for idx, mod in cat if not mod.startswith('_')]
                for cat in tree)

    if filter_text:
        tree = ([(idx, mod) for idx, mod in cat if filter_text in mod.lower()]
                for cat in tree)
    
    return list(tree)


def update_history(new_path, old_path):

    # in case of reload don't change history
    if new_path == old_path:
        return
    
    prefs = get_preferences()
    api_props = get_props()
    history = api_props.history

    if old_path:    # don't add empty path
        # add to history
        hist = history.add()
        hist.name = hist.path = old_path
        
        hist.filter = api_props.filter
        hist.category_toggles = api_props.category_toggles
        hist.page_indices = api_props.page_indices

    # reset props
    api_props.filter = ""
    api_props.category_toggles = (True,) * len(CATEGORIES)
    api_props.page_indices = (1,) * len(CATEGORIES)

    if new_path:
        # check if exists in history
        idx = history.find(new_path)
        if idx != -1:
            hist = history[idx]

            if prefs.restore_history_settings:
                # copy props from history
                api_props.filter = hist.filter
                api_props.category_toggles = hist.category_toggles
                api_props.page_indices = hist.page_indices

            # remove
            history.remove(idx)

    # remove extras
    extra = len(history) - prefs.history_size
    for i in range(extra):
        history.remove(i)



#########################################################################################
# UTILITY FUNCTIONS
#########################################################################################

def evaluate(path):
    """Returns Python Object from String Path"""
    try:
        parts = re.split('([^a-zA-Z0-9_-])', path.strip(), 1) # '-' for 'API_Browser-main'
        if parts[0] in dir(builtins):
            namespace = {}
        else:
            try:
                # replace parts[0] with 'mod' incase of illegal mod-name
                # eg. '-' in 'API_Browser-main'
                namespace = {'mod': __import__(parts[0])}
                parts[0] = 'mod'
            except:
                namespace = {}
        
        return  eval("".join(parts), namespace)
    except Exception as e:
        return e


def parent(path):
    """Returns the parent path"""
    # TODO: fix ['" characters in key
    return path.rpartition('[' if path.endswith(']') else '.')[0]   # rsplit() not used


def resolve_path(path, info):
    """Returns Submodule path from info=(cat, idx, word) tuple"""

    cat, idx, word = info.split(" ", maxsplit=2)
    cat = int(cat)

    if cat == 0:  # key
        key = word
        # escape \' characters
        key = key.replace("\\", "\\\\").replace("'", "\\'")
        path += f"['{key}']"

    elif cat == 1:  # index
        path += f"[{idx}]"

    else:
        if path:
            path += '.'
        path += word

    return path


def get_module_description(path):
    module = evaluate(path)
    desc = str(module)

    if module.__doc__:
        # omit last '.'; blender adds an '.' after
        desc += "\n\n" + str(module.__doc__).rstrip(" .")

    return desc


def isiterable(mod):
    try:
        # (str, byte) can be passed but bpy.app gets ignored
        return iter(mod) and not isinstance(mod, str)
    except:
        return False


# following functions are taken from rlcompleter.py and modified

def get_class_members(klass):
    ret = dir(klass)
    if hasattr(klass,'__bases__'):
        for base in klass.__bases__:
            ret = ret + get_class_members(base)
    return ret


def object_categories(obj):
    
    itm, val, mod, typ, props, struct, met, att, bug = [], [], [], [], [], [], [], [], []

    if isiterable(obj):
        if hasattr(obj, 'keys') \
            and len(obj) == len(obj.keys()): # special check for <class 'bpy_prop_collection'>
            itm = [str(k) for k in obj.keys()]
        else:
            val = [str(v) for v in obj]

    words = set(dir(obj))
    if hasattr(obj, '__class__'):
        words.add('__class__')
        words.update(get_class_members(obj.__class__))
    
    for word in sorted(words):
        try:
            styp = str(type(getattr(obj, word)))
        except:
            bug.append( word )
            continue

        if styp == "<class 'module'>":
            mod.append( word )
        elif styp.startswith("<class 'bpy_prop"):
            props.append( word )
        elif styp.startswith("<class 'bpy"):
            struct.append( word )
        elif styp == "<class 'builtin_function_or_method'>":
            met.append( word )
        elif styp == "<class 'type'>":
            typ.append( word )
        else:
            att.append( word )

    return itm, val, mod, typ, props, struct, met, att, bug
    

def global_categories():

    itm, val, mod, typ, props, struct, met, att, bug = [], [], [], [], [], [], [], [], []
    mod += get_root_modules()

    for word, value in builtins.__dict__.items():
        try:
            styp = str(type(value))
        except:
            bug.append( word )
            continue

        if styp == "<class 'type'>":
            typ.append( word )
        elif styp == "<class 'builtin_function_or_method'>":
            met.append( word )
        else:
            att.append( word )
    
    return itm, val, mod, typ, props, struct, met, att, bug


def categorize_module(path):
    
    if not path:
        return global_categories()

    module = evaluate(path)

    return object_categories(module)


#########################################################################################
# OPERATORS, MENUS
#########################################################################################


class API_OT_History_Clear(Operator):
    """Clears History"""
    bl_idname = "api_browser.history_clear"
    bl_label = "Clear History"

    def execute(self, context):

        api_props = get_props()
        api_props.history.clear()

        self.report({"INFO"}, "History Cleared!")
        return {'FINISHED'}

class API_MT_History_Menu(Menu):
    bl_label = "History"
    bl_idname = "API_MT_History_Menu"

    def draw(self, context):
        
        api_props = get_props()
        history = api_props.history
        layout = self.layout

        for i in range(len(history) - 1, -1, -1):
            item = history[i]
            layout.operator(API_OT_History.bl_idname, text=item.path).index = i
        layout.separator()
        layout.operator(API_OT_History_Clear.bl_idname, text="Clear", icon="CANCEL")


class API_OT_History(Operator, Menu):
    """Show History"""
    bl_label = "History"
    bl_idname = "api_browser.history"

    index: IntProperty(name="index", default=-1)

    @classmethod
    def description(cls, context, properties):

        api_props = get_props()
        idx = properties.index

        if idx == -1:
            return
        
        path = api_props.history[idx].path

        if path:
            return get_module_description(path)

    @classmethod
    def poll(cls, context):
        return get_props().history

    def execute(self, context):

        api_props = get_props()
        idx = self.index

        if idx == -1:
            bpy.ops.wm.call_menu(name=API_MT_History_Menu.bl_idname)
        else:
            hist = api_props.history[idx]
            api_props.path = hist.path
            self.index = -1

        return {'FINISHED'}


class API_OT_GOTO_Parent(Operator):
    """Go to parent Module"""
    bl_idname = "api_browser.goto_parent_module"
    bl_label = "Parent"

    @classmethod
    def poll(cls, context):
        return get_props().path

    @classmethod
    def description(cls, context, properties):
        api_props = get_props()
        path = parent(api_props.path)

        if path:
            return get_module_description(path)

    def execute(self, context):

        api_props = get_props()
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
        api_props = get_props()
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
        api_props = get_props()
        path = resolve_path(api_props.path, properties.info)

        if path:
            return get_module_description(path)

    def execute(self, context):

        api_props = get_props()
        api_props.path = resolve_path(api_props.path, self.info)

        return {'FINISHED'}


class API_OT_Reload_Module(Operator):
    """Reloads the Current module"""
    bl_idname = "api_browser.reload"
    bl_label = "Reload"

    def execute(self, context):

        get_data_tree(reload=True)

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
        return get_props().path

    def execute(self, context):
        return {'CANCELLED'}

    def invoke(self, context, event):
        path = get_props().path
        self.module = evaluate(path)
        return context.window_manager.invoke_popup(self, width=600)

    def draw(self, context):
        path = get_props().path
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

        prefs = get_preferences()
        api_props = get_props()

        data_tree = get_data_tree(update=True)
        columns = prefs.columns
        rows = prefs.rows
        count = rows * columns

        layout = self.layout
        col = layout.column(align=True)

        # path bar
        row = col.row(align=True)
        row.prop(api_props, 'path', text='')
        row.operator(API_OT_Copy_Text.bl_idname, text="",
                     icon="COPYDOWN", emboss=False).text = api_props.path
        if not prefs.auto_reload: row.operator(API_OT_Reload_Module.bl_idname,
                     text="", icon="FILE_REFRESH")
        row.operator(API_OT_Module_Info.bl_idname, text="", icon="INFO")

        # navigation bar
        row = col.row(align=True)
        row.operator(API_OT_GOTO_Parent.bl_idname, text="Parent", icon="BACK")
        row.operator(API_OT_GOTO_Default.bl_idname, text=prefs.default_module,
                     emboss=True, icon="FILE_PARENT")

        # history
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
            c_enabled = api_props.category_toggles[i]

            page_index = api_props.page_indices[i]
            page_index = min(page_index, -(len(category) // -count)) # ceil div
            api_props.page_indices[i] = page_index

            start = (page_index -1) * count
            end = min(start+count, len(category))

            overflow = len(category) > count

            row = box.row()
            if overflow:
                split = row.split(factor=0.8)
                row = split.row()

            row.alignment = 'LEFT'
            # category label
            label = f"{c_label} ({start+1}-{end} / {len(category)})" if overflow \
                    else f"{c_label} ({len(category)})"
            row.prop(api_props, "category_toggles", index=i, text=label, emboss=False,
                    icon="DOWNARROW_HLT" if c_enabled else "RIGHTARROW",)
            
            if overflow:
                row = split.row()
                row.alignment = 'RIGHT'
                row.prop(api_props, "page_indices", index=i, text="")

            if c_enabled:
                # items
                col = box.column(align=True)
                row = col.row(align=True) # fix for a bug when count isnt't multiple of columns
                for j, (idx, entry) in zip(range(start, end),category[start:]):
                    if not (j % columns):
                        row = col.row(align=True)

                    row.operator(API_OT_GOTO_Sub_Module.bl_idname,
                                 text=str(entry),
                                 emboss=True,
                    ).info = f'{i} {idx} {entry}'

        return


class APIBrowserAddonPreferences(AddonPreferences):
    bl_idname = __name__

    default_module: StringProperty(
        name="Default Module",
        description="Default module to display",
        default="bpy",
    )
    columns: IntProperty(
        name="Columns",
        description="Column count",
        default=3,
        min=1,
    )
    rows: IntProperty(
        name="Rows",
        description="Rows count",
        default=10,
        min=1,
    )
    history_size: IntProperty(
        name="History Size",
        description="Number of history items to keep",
        default=10,
        min=1
    )
    restore_history_settings: BoolProperty(
        name="Restore History Settings",
        description="Restores filters, category toggles, page indices etc",
        default=True,
    )
    auto_reload: BoolProperty(
        name="Auto Reload",
        description="Automatically Reload Modules",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        col = layout.column(align=True)
        col.prop(self, "default_module")
        col.prop(self, "columns")
        col.prop(self, "rows")
        col.prop(self, "history_size")
        col.prop(self, "restore_history_settings")
        col.prop(self, "auto_reload")


#########################################################################################
# PROPERTIES
#########################################################################################

class API_History_Props(PropertyGroup):

    path: StringProperty(
        name="Path",
        description="API path",
        # default="bpy",
    )
    filter: StringProperty(
        name="Filter",
        description="Filters matching entries",
        default="",
        options={'TEXTEDIT_UPDATE'},
    )
    category_toggles: BoolVectorProperty(
        name="Category Toggles",
        description="Expand/Collapse Category",
        default=(True,) * len(CATEGORIES),
        size=len(CATEGORIES),
    )
    page_indices: IntVectorProperty(
        name="Page Indices",
        description="Current page indices",
        default=(1,) * len(CATEGORIES),
        size=len(CATEGORIES),
        min=1,
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
    old_path: StringProperty(
        name="Old Path",
        description="Old API path",
        default=""
    )
    filter: StringProperty(
        name="Filter",
        description="Filters matching entries",
        default="",
        options={'TEXTEDIT_UPDATE'},
    )
    category_toggles: BoolVectorProperty(
        name="Category Toggles",
        description="Expand/Collapse Category",
        default=(True,) * len(CATEGORIES),
        size=len(CATEGORIES),
    )
    page_indices: IntVectorProperty(
        name="Page Indices",
        description="Current page indices",
        default=(1,) * len(CATEGORIES),
        size=len(CATEGORIES),
        min=1,
    )

    filter_internal: BoolProperty(
        name="Filter Internal",
        description="Filters entries starting with '_'",
        default=True,
    )
    history: CollectionProperty(
        type=API_History_Props,
        name="API History Props",
        description="Previous Paths",
    )


#########################################################################################
# REGISTER/UNREGISTER
#########################################################################################


classes = (
    API_MT_History_Menu,
    API_OT_History_Clear,
    API_OT_History,
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
    )

    get_props().path = get_preferences().default_module


def unregister():

    del bpy.types.WindowManager.api_props

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
