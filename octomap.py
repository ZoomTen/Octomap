from tkinter import *
from tkinter.ttk import *
from tkinter.messagebox import showerror, showinfo, askyesno
from tkinter.filedialog import askopenfilename, asksaveasfilename, askdirectory
from tkinter.scrolledtext import ScrolledText
import math
from PIL import Image, ImageTk
import re
import os, sys
import subprocess
from pathlib import Path
from configparser import ConfigParser

__VERSION__ = "0.0.3"

__DISPLAY_POINTLESS_BITMAPS__ = True

__CONFIG__ = os.path.join(
	os.path.realpath(os.path.dirname(__file__)),
	"octomap.ini"
)

class AppState(object):
	"""
	State of the entire application.
	"""
	# blocks
	loaded_block_file = None
	block_size = (0, 0)
	block_readout = [] # raw data
	
	# metatiles
	loaded_metatile_file = None
	which_metatile = 0 # is being selected
	metatile_readout = [] # raw data
	
	# tiles / gfx
	loaded_tile_file = None
	tile_images = [] # PIL images
	
	# events
	loaded_event_file = None
	loaded_events = {
		"event": [],
		"warp": [],
		"coord": [],
		"bg": []
	}
	loaded_event_file_is_new_styled = False
	
	scale_factor = 1
	
	text_editor = "C:/Documents and Settings/Zumi/Desktop/Applications/xse/XTE/Build/XTE.exe"

	def validate_block_size():
		with open(AppState.loaded_block_file, "rb") as blocks:
			raw = blocks.read()
			width, height = AppState.block_size
			if len(raw) != (width * height):
				showerror("Invalid block size", "can't load %s:\n\nMap length (%d) not equal to width (%d) x height (%d)" % (
					AppState.loaded_block_file, len(raw), width, height
				))
				AppState.loaded_block_file = None
				AppState.block_size = (0, 0)
				AppState.block_readout = []
			else:
				AppState.block_readout = [[int(b) for b in raw[i:i+width]] for i in range(0,len(raw), width)]
	
	def validate_metatiles():
		with open(AppState.loaded_metatile_file, "rb") as metatiles:
			raw = metatiles.read()
			AppState.metatile_readout = [[int(b) for b in raw[i:i+16]] for i in range(0,len(raw), 16)]
			AppState.which_metatile = 0
	
	def validate_tiles():
		AppState.tile_images = []
		im = Image.open(AppState.loaded_tile_file) 
		w, h = im.size
		for v in range(0, h, 8):
			for h in range(0, w, 8):
				AppState.tile_images.append(im.crop(
					(h, v, h+8, v+8)
				))
		# take into account 2nd vram bank
		if len(AppState.tile_images) > 0x60:
			for i in range(0x20):
				AppState.tile_images.insert(0x60, AppState.tile_images[0])
	
	def validate_events():
		AppState.loaded_event_file_is_new_styled = False
		with open(AppState.loaded_event_file, "r") as asm:
			line_no = 1
			AppState.loaded_events["event"] = []
			AppState.loaded_events["warp"] = []
			AppState.loaded_events["coord"] = []
			AppState.loaded_events["bg"] = []
			line = asm.readline()
			while line:
				working_line = line
				starting_line_no = line_no
				while len(re.findall(r"\\\s*$", line)) > 0:
					working_line = re.sub(r"\\\s*$", "", working_line)
					line = asm.readline()
					line_no += 1
					working_line += re.sub(r"\\\s*$", "", line).strip()
				
				is_comment = len(re.findall(r"^\s*;", working_line)) != 0
				AppState.loaded_event_file_is_new_styled |= len(re.findall(r"def_(warp|coord|bg|object)_events", working_line)) > 0
				AppState.loaded_events["event"] += [[j.strip() for j in i.groups()] + [starting_line_no, is_comment] for i in (re.finditer(r"object_event\s+(\d+),\s+(\d+),(.+)", working_line))]
				AppState.loaded_events["warp"]  += [[j.strip() for j in i.groups()] + [starting_line_no, is_comment] for i in (re.finditer(r"warp_event\s+(\d+),\s+(\d+),(.+)", working_line))]
				AppState.loaded_events["coord"] += [[j.strip() for j in i.groups()] + [starting_line_no, is_comment] for i in (re.finditer(r"coord_event\s+(\d+),\s+(\d+),(.+)", working_line))]
				AppState.loaded_events["bg"]    += [[j.strip() for j in i.groups()] + [starting_line_no, is_comment] for i in (re.finditer(r"bg_event\s+(\d+),\s+(\d+),(.+)", working_line))]
				line = asm.readline()
				line_no += 1
#################################################################################################

# utility functions

canvas2block_coord = lambda x: int(x//8//4//AppState.scale_factor)
block2canvas_coord = lambda x: int(x*8*4*AppState.scale_factor)
canvas2event_coord = lambda x: int(x//8//2//AppState.scale_factor)
event2canvas_coord = lambda x: int(x*8*2*AppState.scale_factor)

#################################################################################################

# https://blog.teclado.com/tkinter-scrollable-frames/
class ScrollableFrame(Frame):
	'''
	Scrollable Frames in Tkinter
	
	by Jose Salvatierra, 10 Oct. 2019
	'''
	def __init__(self, container, *args, **kwargs):
		super().__init__(container)
		canvas = Canvas(self, *args, **kwargs)
		scrollbar = Scrollbar(self, orient="vertical", command=canvas.yview)
		self.frame = Frame(canvas)

		self.frame.bind(
			"<Configure>",
			lambda e: canvas.configure(
				scrollregion=canvas.bbox("all")
			)
		)

		canvas.create_window((0, 0), window=self.frame, anchor="nw")

		canvas.configure(yscrollcommand=scrollbar.set)

		canvas.pack(side="left", fill="both", expand=True)
		scrollbar.pack(side="right", fill="y")

#################################################################################################

# https://stackoverflow.com/a/41080067
class CanvasTooltip:
	'''
	It creates a tooltip for a given canvas tag or id as the mouse is
	above it.

	This class has been derived from the original Tooltip class I updated
	and posted back to StackOverflow at the following link:

	https://stackoverflow.com/questions/3221956/
		   what-is-the-simplest-way-to-make-tooltips-in-tkinter/
		   41079350#41079350

	Alberto Vassena on 2016.12.10.
	'''

	def __init__(self, canvas, tag_or_id,
				 *,
				 pad=(5, 3, 5, 3),
				 text='canvas info',
				 waittime=400,
				 wraplength=250):
		self.waittime = waittime  # in miliseconds, originally 500
		self.wraplength = wraplength  # in pixels, originally 180
		self.canvas = canvas
		self.text = text
		self.canvas.tag_bind(tag_or_id, "<Enter>", self.onEnter)
		self.canvas.tag_bind(tag_or_id, "<Leave>", self.onLeave)
		self.canvas.tag_bind(tag_or_id, "<ButtonPress>", self.onLeave)
		self.pad = pad
		self.id = None
		self.tw = None

	def onEnter(self, event=None):
		self.schedule()

	def onLeave(self, event=None):
		self.unschedule()
		self.hide()

	def schedule(self):
		self.unschedule()
		self.id = self.canvas.after(self.waittime, self.show)

	def unschedule(self):
		id_ = self.id
		self.id = None
		if id_:
			self.canvas.after_cancel(id_)

	def show(self, event=None):
		def tip_pos_calculator(canvas, label,
							   *,
							   tip_delta=(10, 5), pad=(5, 3, 5, 3)):

			c = canvas

			s_width, s_height = c.winfo_screenwidth(), c.winfo_screenheight()

			width, height = (pad[0] + label.winfo_reqwidth() + pad[2],
							 pad[1] + label.winfo_reqheight() + pad[3])

			mouse_x, mouse_y = c.winfo_pointerxy()

			x1, y1 = mouse_x + tip_delta[0], mouse_y + tip_delta[1]
			x2, y2 = x1 + width, y1 + height

			x_delta = x2 - s_width
			if x_delta < 0:
				x_delta = 0
			y_delta = y2 - s_height
			if y_delta < 0:
				y_delta = 0

			offscreen = (x_delta, y_delta) != (0, 0)

			if offscreen:

				if x_delta:
					x1 = mouse_x - tip_delta[0] - width

				if y_delta:
					y1 = mouse_y - tip_delta[1] - height

			offscreen_again = y1 < 0  # out on the top

			if offscreen_again:
				# No further checks will be done.

				# TIP:
				# A further mod might automagically augment the
				# wraplength when the tooltip is too high to be
				# kept inside the screen.
				y1 = 0

			return x1, y1

		pad = self.pad
		canvas = self.canvas

		# creates a toplevel window
		self.tw = Toplevel(canvas.master)

		# Leaves only the label and removes the app window
		self.tw.wm_overrideredirect(True)

		win = Frame(self.tw,
					   borderwidth=0)
		label = Label(win,
						  text=self.text,
						  justify=LEFT,
						  borderwidth=0,
						  wraplength=self.wraplength)

		label.grid(padx=(pad[0], pad[2]),
				   pady=(pad[1], pad[3]),
				   sticky=NSEW)
		win.grid()

		x, y = tip_pos_calculator(canvas, label)

		self.tw.wm_geometry("+%d+%d" % (x, y))

	def hide(self):
		if self.tw:
			self.tw.destroy()
		self.tw = None

#################################################################################################

class App(Tk):
	"""
	Main application
	"""
	def __init__(self):
		super().__init__()
		self.title("Octomap")
		
		# set icon
		iconphoto = PhotoImage(file=os.path.join(
			os.path.realpath(os.path.dirname(__file__)),
			"octomap.png"
		))
		self.iconphoto(False, iconphoto)
		
		# menu bar
		menu_bar = Menu(self)
		self.config(menu=menu_bar)
		
		# menus
		file_menu = Menu(menu_bar, tearoff=0)
		file_menu.add_command(label="Guess settings from project...", command=self.guess_settings, accelerator="Ctrl+G")
		self.bind("<Control-g>", lambda _: self.guess_settings())
		file_menu.add_command(label="Load settings", command=self.load_settings, accelerator="Ctrl+O")
		self.bind("<Control-o>", lambda _: self.load_settings())
		file_menu.add_command(label="Save settings", command=self.save_settings, accelerator="Ctrl+S")
		self.bind("<Control-s>", lambda _: self.save_settings())
		file_menu.add_separator()
		file_menu.add_command(label="Exit", command=sys.exit)
		menu_bar.add_cascade(label="File",menu=file_menu)
		
		self.edit_menu = Menu(menu_bar, tearoff=0)
		#edit_menu.add_command(label="Undo [TODO]", accelerator="Ctrl+Z")
		#edit_menu.add_command(label="Redo [TODO]", accelerator="Ctrl+Y")
		
		def add_new_event(event_type):
			self.frm_map_area.save_events()
			AppState.loaded_events[event_type].append(
				["0", "0", "", 1, False]
			)
			self.frm_map_area.status.set("new %s event added at (0, 0)" % event_type)
			self.frm_map_area.update_events()
		
		add_menu = Menu(self.edit_menu, tearoff=0)
		add_menu.add_command(label="Background event", command=lambda:add_new_event("bg"))
		add_menu.add_command(label="Object event", command=lambda:add_new_event("event"))
		add_menu.add_command(label="Coordinate event", command=lambda:add_new_event("coord"))
		add_menu.add_command(label="Warp", command=lambda:add_new_event("warp"))
		self.edit_menu.add_cascade(label="Add new...",menu=add_menu, state="disabled")
		
		self.edit_menu.add_separator()
		self.edit_menu.add_command(label="Preferences", command=self.open_preferences)
		menu_bar.add_cascade(label="Edit",menu=self.edit_menu)
		
		help_menu = Menu(menu_bar, tearoff=0)
		help_menu.add_command(label="Short guide", command=self.help_screen, accelerator="Ctrl+H")
		self.bind("<Control-h>", lambda _: self.help_screen())
		help_menu.add_command(label="About", command=self.about_screen)
		menu_bar.add_cascade(label="Help",menu=help_menu)
		
		# min dimensions
		self.rowconfigure(0, minsize=500, weight=1)
		self.columnconfigure(1, weight=1)

		# status bar
		self.status = StringVar()
		self.status_message = ''
		self.sbar = Label(self, anchor='w', justify="left", textvariable=self.status, relief=SUNKEN)
		
		# button container
		frm_buttons = ScrollableFrame(self, width=112)
		
		# set styles
		s = Style()
		
		# set arial font on windows
		if self.tk.call("tk", "windowingsystem") == "win32":
			s.configure(".", font=("Arial", "9"))
		else:
			# set theme outside windows
			s.theme_use("clam")
		
		# add pointless logo
		if __DISPLAY_POINTLESS_BITMAPS__:
			frm_pointless_logo = Frame(self, style="PointlessLogo.TFrame")
			frm_pointless_logo_centering = Frame(frm_pointless_logo)
			self.logo = PhotoImage(file=os.path.join(
				os.path.realpath(os.path.dirname(__file__)),
				"octomap_header.png"
			))
			s.configure("PointlessLogo.TFrame", background="black", padding=0)
			s.configure("PointlessLogo.TLabel", background="black")
			lbl_logo = Label(frm_pointless_logo_centering, image=self.logo, style="PointlessLogo.TLabel")
			lbl_logo.grid(row=0, column=0, sticky="ew")
			frm_pointless_logo_centering.pack(side=TOP, fill=Y)
			frm_pointless_logo.pack(side=TOP, fill=X)
		
		# compose the UI
		self.frm_map_area = MapView(self)
		self.frm_map_palette = MapPalette(self)
		self.sbar.pack(side=BOTTOM, fill=X, padx=5, pady=5)
		frm_buttons.pack(side=LEFT, fill=Y, padx=5)
		self.frm_map_area.pack(side=LEFT, fill=BOTH, expand=1)
		self.frm_map_palette.pack(side=LEFT, fill=Y, padx=5)
		
		# compose LHS buttons menu
		lbl_block = Labelframe(frm_buttons.frame, text="Blocks")
		btn_open_block = Button(lbl_block, text="Open", command=self.open_block)
		self.btn_reload_block = Button(lbl_block, text="Reload", command=self.reload_blocks, state="disabled")
		self.btn_save_block = Button(lbl_block, text="Save As", command=self.save_block_as, state="disabled")
		
		lbl_block.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
		btn_open_block.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
		self.btn_reload_block.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
		self.btn_save_block.grid(row=3, column=0, sticky="ew", padx=5, pady=5)
		
		lbl_metatiles = Labelframe(frm_buttons.frame, text="Metatiles")
		btn_open_metatiles = Button(lbl_metatiles, text="Open", command=self.open_meta)
		
		lbl_metatiles.grid(row=4, column=0, sticky="ew", padx=5, pady=5)
		btn_open_metatiles.grid(row=5, column=0, sticky="ew", padx=5, pady=5)
		
		lbl_tiles = Labelframe(frm_buttons.frame, text="GFX")
		btn_open_tiles = Button(lbl_tiles, text="Open", command=self.open_tile)
		
		lbl_tiles.grid(row=6, column=0, sticky="ew", padx=5, pady=5)
		btn_open_tiles.grid(row=7, column=0, sticky="ew", padx=5, pady=5)
		
		lbl_events = Labelframe(frm_buttons.frame, text="Events")
		btn_open_events = Button(lbl_events, text="Open", command=self.open_event)
		self.btn_look_events = Button(lbl_events, text="See Code", command=self.see_code, state="disabled")
		self.btn_reload_events = Button(lbl_events, text="Reload", command=self.reload_events, state="disabled")
		self.btn_editor_events = Button(lbl_events, text="Open in Editor", command=self.editor_events, state="disabled")
		
		lbl_events.grid(row=8, column=0, sticky="ew", padx=5, pady=5)
		btn_open_events.grid(row=9, column=0, sticky="ew", padx=5, pady=5)
		self.btn_reload_events.grid(row=10, column=0, sticky="ew", padx=5, pady=5)
		self.btn_look_events.grid(row=11, column=0, sticky="ew", padx=5, pady=5)
		self.btn_editor_events.grid(row=12, column=0, sticky="ew", padx=5, pady=5)
		
		lbl_edit = Label(frm_buttons.frame, text="")
		btn_update = Button(frm_buttons.frame, text="Reload All", command=self.update_all)
		
		lbl_edit.grid(row=13, column=0, sticky="ew", padx=5, pady=5)
		btn_update.grid(row=15, column=0, sticky="ew", padx=5, pady=5)
		
		self.check_params()
		self.load_preference_config()
		
		# load settings if specified
		if len(sys.argv) > 1:
			fp = Path(sys.argv[1])
			if fp.is_file():
				self.load_settings_from_file(str(fp.resolve()))
	
	def open_preferences(self):
		return PreferencesScreen(self)
	
	def about_screen(self):
		return AboutScreen(self)
		
	def guess_settings(self):
		should_reload = GuessSettings(self).show()
		if should_reload:
			self.check_params()
	
	def load_settings(self):
		filepath = askopenfilename(
			filetypes=[("Settings file", "*.ini"), ("All Files", "*.*")]
		)
		if not filepath:
			return
		self.load_settings_from_file(filepath)
	
	def load_preference_config(self):
		if Path(__CONFIG__).is_file():
			cfg = ConfigParser()
			cfg.read(__CONFIG__)
			cfg_p = cfg["Settings"]
			
			if cfg_p.get("editor", None):
				AppState.text_editor = cfg_p["editor"]
			
			if cfg_p.get("scale_factor", None):
				AppState.scale_factor = int(cfg_p["scale_factor"])
	
	def load_settings_from_file(self, filepath):
		cfg = ConfigParser()
		cfg.read(filepath)
		cfg_p = cfg["Octomap Project"]
		
		if cfg_p.get("blocks", None):
			AppState.loaded_block_file = cfg_p["blocks"]
		else:
			AppState.loaded_block_file = None
		
		AppState.block_size = (
			int(cfg_p["mapsize_w"]),
			int(cfg_p["mapsize_h"])
		)
		
		if cfg_p.get("metatiles", None):
			AppState.loaded_metatile_file = cfg_p["metatiles"]
		else:
			AppState.loaded_metatile_file = None
		
		if cfg_p.get("tiles", None):
			AppState.loaded_tile_file = cfg_p["tiles"]
		else:
			AppState.loaded_tile_file = None
		
		if cfg_p.get("events", None):
			AppState.loaded_event_file = cfg_p["events"]
		else:
			AppState.loaded_event_file = None
		
		self.check_params()
	
	def save_settings(self):
		filepath = asksaveasfilename(
			filetypes=[("Settings file", "*.ini"), ("All Files", "*.*")]
		)
		if not filepath:
			return
		cfg = ConfigParser()
		cfg["Octomap Project"] = {
			"blocks": AppState.loaded_block_file if AppState.loaded_block_file else "",
			"mapsize_w": AppState.block_size[0],
			"mapsize_h": AppState.block_size[1],
			"metatiles": AppState.loaded_metatile_file if AppState.loaded_metatile_file else "",
			"tiles": AppState.loaded_tile_file if AppState.loaded_tile_file else "",
			"events": AppState.loaded_event_file if AppState.loaded_event_file else ""
		}
		with open(filepath, "w") as cfgfile:
			cfg.write(cfgfile)
	
	def see_code(self):
		if AppState.loaded_event_file_is_new_styled:
			text = """	db 0, 0 ; filler
	
	def_warp_events
	%s
	
	def_coord_events
	%s
	
	def_bg_events
	%s
	
	def_object_events
	%s
""" % (
	"\n\t".join(["%swarp_event %3d, %3d, %s" % (
		("; " if i[4] else ""),
		int(i[0]), int(i[1]), i[2]) for i in AppState.loaded_events["warp"]]
	),
	"\n\t".join(["%scoord_event %3d, %3d, %s" % (
		("; " if i[4] else ""),
		int(i[0]), int(i[1]), i[2]) for i in AppState.loaded_events["coord"]]
	),
	"\n\t".join(["%sbg_event %3d, %3d, %s" % (
		("; " if i[4] else ""),
		int(i[0]), int(i[1]), i[2]) for i in AppState.loaded_events["bg"]]
	),
	"\n\t".join(["%sobject_event %3d, %3d, %s" % (
		("; " if i[4] else ""),
		int(i[0]), int(i[1]), i[2]) for i in AppState.loaded_events["event"]]
	),
)
		else:
			text = """	db 0, 0 ; filler
	
	db %d ; warp events
	%s
	
	db %d ; coord events
	%s
	
	db %d ; bg events
	%s
	
	db %d ; object events
	%s
""" % (
	len(list(filter(lambda x: not x[4], AppState.loaded_events["warp"]))),
	"\n\t".join(["%swarp_event %3d, %3d, %s" % (
		("; " if i[4] else ""),
		int(i[0]), int(i[1]), i[2]) for i in AppState.loaded_events["warp"]]
	),
	len(list(filter(lambda x: not x[4], AppState.loaded_events["coord"]))),
	"\n\t".join(["%scoord_event %3d, %3d, %s" % (
		("; " if i[4] else ""),
		int(i[0]), int(i[1]), i[2]) for i in AppState.loaded_events["coord"]]
	),
	len(list(filter(lambda x: not x[4], AppState.loaded_events["bg"]))),
	"\n\t".join(["%sbg_event %3d, %3d, %s" % (
		("; " if i[4] else ""),
		int(i[0]), int(i[1]), i[2]) for i in AppState.loaded_events["bg"]]
	),
	len(list(filter(lambda x: not x[4], AppState.loaded_events["event"]))),
	"\n\t".join(["%sobject_event %3d, %3d, %s" % (
		("; " if i[4] else ""),
		int(i[0]), int(i[1]), i[2]) for i in AppState.loaded_events["event"]]
	),
)
		ScrolledInfoWindow(parent=self, title="Event code (ctrl+a, ctrl+c to copy)", text=text)
	def help_screen(self):
		ScrolledInfoWindow(parent=self, title="Help", text="""
Octomap
=======

Loading the map
---------------
Load in blocks (.blk), metatiles (.bin), graphics (.png) and events (.asm)
from the lefthand side menu.

You will be prompted for the map size when loading in blocks.
WIDTH x HEIGHT must match the size of the .blk file itself.

Events must contain object_events, coord_events, bg_events and warp_events.

The "Reload All" button reloads the map completely.

"Reload" in the Events panel will only reload the events file.

The status pile at the bottom should let you know when everything is ready.

You can also quickly load maps through File -> Guess settings and
supply a disassembly project directory. They must have the following
folders in it:
	- data/tilesets/ (contains *_metatiles.bin files)
	- gfx/tilesets/  (contains *.png files)
	- maps/          (contains *.blk and *.asm files)

Editing the map
---------------
The middle screen contains the map view. Its status bar lets you know
the cursor position on the map as well as for event positioning.

Left click on a map's tile to overwrite it with the selected metatile.
Upon load, this will be metatile 0x00.

Right click on a map's tile to "eyedrop" it.

Click and drag an event (colored squares) to move it around.
Right-click the event to show options.
Double-click the event to edit it here.
Hover over the event to quickly view what properties are in it.

Left click on the righthand side menu to select a metatile from
the list. The status bar will let you know which metatile you're hovering
above as well as the currently selected metatile.

You can open an event in an external text editor, which should
jump to the line it's in (set it in Edit->Preferences; it should
support Sublime Text-styled command line syntax)
""")

	def open_block(self):
		filepath = askopenfilename(
			filetypes=[("Blocks", "*.blk"), ("All Files", "*.*")]
		)
		if not filepath:
			return
		map_dimensions = MapSize(self).show()
		if map_dimensions:
			AppState.loaded_block_file = filepath
			AppState.block_size = map_dimensions
			AppState.validate_block_size()
		self.check_params()
	
	def save_block_as(self):
		if len(AppState.block_readout) == 0:
			showerror(
				"Blocks empty",
				"Resulting file would be empty... load or create some blocks first?"
			)
			return
		filepath = asksaveasfilename(
			filetypes=[("Blocks", "*.blk"), ("All Files", "*.*")]
		)
		if not filepath:
			return
		with open(filepath, "wb") as exported_map:
			for y in AppState.block_readout:
				for x in y:
					exported_map.write(x.to_bytes(1,'little'))

	def open_meta(self):
		filepath = askopenfilename(
			filetypes=[("Metatiles", "*.bin"), ("All Files", "*.*")]
		)
		if not filepath:
			return
		AppState.loaded_metatile_file = filepath
		#AppState.validate_metatiles()
		self.check_params()

	def open_tile(self):
		filepath = askopenfilename(
			filetypes=[("Images", "*.png"), ("All Files", "*.*")]
		)
		if not filepath:
			return
		AppState.loaded_tile_file = filepath
		#AppState.validate_tiles()
		self.check_params()

	def open_event(self):
		filepath = askopenfilename(
			filetypes=[("Map code", "*.asm"), ("All Files", "*.*")]
		)
		if not filepath:
			return
		AppState.loaded_event_file = filepath
		self.check_params()
	
	def reload_events(self):
		AppState.validate_events()
		self.frm_map_area.update_events()

	def editor_events(self):
		command = [
			str(Path(AppState.text_editor).resolve()),
			str(Path(AppState.loaded_event_file).resolve())
		]
		subprocess.Popen(command, shell=True)
	
	def reload_blocks(self):
		AppState.validate_block_size()
		self.frm_map_area.update_blocks()
	
	def check_params(self):
		self.status_message = "Everything seems OK, click on 'Reload All' to load full map"
		
		if not AppState.loaded_event_file:
			self.status_message = "No event file loaded"
			self.update_status()
			return False
		
		self.btn_editor_events.config(state="normal")
		
		if not AppState.loaded_block_file:
			self.status_message = "No block file loaded"
			self.update_status()
			return False
		
		if not AppState.loaded_metatile_file:
			self.status_message = "No metatile file loaded"
			self.update_status()
			return False
		
		if not AppState.loaded_tile_file:
			self.status_message = "No tileset file loaded"
			self.update_status()
			return False
		
		self.update_status()
		return True
		
	def update_all(self):
		if not self.check_params():
			showerror(
				"Parameters not set",
				"Load all needed files first (blocks, metatiles, GFX, events)"
			)
			return
		AppState.validate_block_size()
		AppState.validate_metatiles()
		AppState.validate_tiles()
		AppState.validate_events()
		self.frm_map_palette.update_palette()
		self.frm_map_area.update_map()
		self.edit_menu.entryconfig("Add new...", state="normal")
		self.btn_reload_block.config(state="normal")
		self.btn_reload_events.config(state="normal")
		self.btn_save_block.config(state="normal")
		self.btn_look_events.config(state="normal")
	
	def update_status(self):
		self.status.set("Blocks: %s (%dx%d),\nMetatiles: %s,\nTiles: %s,\nEvents: %s\n----\n%s" % (
			AppState.loaded_block_file, AppState.block_size[0], AppState.block_size[1],
			AppState.loaded_metatile_file,
			AppState.loaded_tile_file,
			AppState.loaded_event_file,
			self.status_message
		))

#################################################################################################

class ScrolledInfoWindow(Toplevel):
	def __init__(self, parent=None, title="Info window", text="Text"):
		super().__init__(parent)
		self.title(title)
		txt = ScrolledText(self)
		txt.insert("end", text)
		txt.configure(state=DISABLED)
		txt.bind("<1>", lambda ev: txt.focus_set())
		txt.pack(expand=True, fill='both')

#################################################################################################

class AboutScreen(Toplevel):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.title("About")
		self.resizable(False, False)
		
		s = Style()
		s.configure("AboutScreen.TLabel", padding=2)
		
		if __DISPLAY_POINTLESS_BITMAPS__:
			self.image = PhotoImage(file=os.path.join(
				os.path.realpath(os.path.dirname(__file__)),
				"octomap_about.png"
			))
			label_image = Label(self, image=self.image, style="AboutScreen.TLabel")
			label_image.grid(row=1, column=1)
		text = """
Octomap %s

\u00a9 2022  Zumi

A program to edit disassembly maps for ROM hacking.
Knockoff of a way better program.
		""" % (
			__VERSION__
		)
		label = Label(self, text=text, style="AboutScreen.TLabel")
		label.grid(row=1, column=2)
		sep = Separator(self, style="AboutScreen.TSeparator",orient='horizontal')
		sep.grid(row=2, column=1, columnspan=3, pady=8, sticky="we")
		ok = Button(self, text="OK", style="AboutScreen.TButton", command=self.destroy)
		ok.grid(row=3, column=3, pady=8, padx=8)

#################################################################################################

class MapSize(Toplevel):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.title("Map size")
		if self.tk.call("tk", "windowingsystem") == "win32":
			self.wm_attributes("-toolwindow", True)
		self.resizable(False, False)
		self.grab_set()
		
		self.width = IntVar()
		self.width.set(1)
		self.height = IntVar()
		self.height.set(1)
		self.width_set = Spinbox(self, from_=1, to=30, width=3, textvariable=self.width, font=('TkDefaultFont',18))
		self.height_set = Spinbox(self, from_=1, to=30, width=3, textvariable=self.height, font=('TkDefaultFont',18))
		label_width = Label(self, text="width")
		label_height = Label(self, text="height")
		x = Label(self, text ="x")
		
		label_width.grid(row=2,column=1, sticky="w", padx=5, pady=5)
		label_height.grid(row=2,column=3, sticky="e", padx=5, pady=5)
		
		self.width_set.grid(row=1,column=1, sticky="w", padx=5, pady=5)
		x.grid(row=1,column=2, sticky="ew", padx=5, pady=5)
		self.height_set.grid(row=1,column=3, sticky="e", padx=5, pady=5)
		
		self.btn_ok = Button(self, text="OK", command=self.do_btn_ok)
		self.btn_cancel = Button(self, text="Cancel", command=self.do_btn_cancel)
		
		self.btn_ok.grid(row=1, column=4, sticky="we", padx=5, pady=5)
		self.btn_cancel.grid(row=2, column=4, sticky="we", padx=5, pady=5)
		
		self.selection_confirmed = False
	
	def do_btn_cancel(self):
		self.destroy()
	
	def do_btn_ok(self):
		self.selection_confirmed = True
		self.destroy()
		
	def show(self):
		self.deiconify()
		self.wait_window()
		if not self.selection_confirmed:
			return False
		return (self.width.get(), self.height.get())

#################################################################################################

class PreferencesScreen(Toplevel):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.title("Preferences")
		self.resizable(False, False)
		self.columnconfigure(1, weight=3)
		self.grab_set()
		
		frame = Frame(self, padding="10 10 12 12")
		frame.grid(column=0, row=0, sticky="news")
		
		self.text_editor = StringVar()
		self.text_editor.set(AppState.text_editor)
		lbl_editor = Label(frame, text="Text editor", anchor="e")
		ety_editor = Entry(frame,textvariable=self.text_editor, width=56)
		btn_load = Button(frame, text="Open\u2026", width=6, command=self.open_executable)
		lbl_editor.grid(column=0, row=0, pady=8, padx=4, sticky="we")
		ety_editor.grid(column=1, row=0, sticky="we", padx=4)
		btn_load.grid(column=2, row=0, sticky="we")
		
		lbl_editor_tip = Label(frame, text="Preferably one that supports Sublime Text-styled command line arguments to instantly jump to a line in a file, e.g.:\n\nTextEditor.exe C:\\Users\\Me\\Desktop\\Thing.txt:25", anchor="w", wraplength=400)
		lbl_editor_tip.grid(column=1, row=1, columnspan=2, sticky="we")
		
		self.scale_factor = IntVar()
		self.scale_factor.set(AppState.scale_factor)
		
		self.old_scale_factor = AppState.scale_factor
		
		lbl_scale_factor = Label(frame, text="Scale factor", anchor="e")
		sbx_scale_factor = Spinbox(frame, from_=1, to=30, width=56, textvariable=self.scale_factor)
		lbl_scale_factor.grid(column=0, row=2, pady=8, padx=4, sticky="we")
		sbx_scale_factor.grid(column=1, row=2, sticky="we", columnspan=2, padx=4)
		
		sep = Separator(frame, orient="horizontal")
		
		sep.grid(column=0, row=3, columnspan=3, sticky="we", pady=4)
		
		btn_cancel = Button(frame, text="Cancel", width=6, command=self.destroy)
		btn_ok = Button(frame, text="OK", width=4, command=self.apply_settings)
		btn_cancel.grid(column=1, row=4, sticky="e", padx=4)
		btn_ok.grid(column=2, row=4, sticky="we")

	def open_executable(self):
		filepath = askopenfilename(
			filetypes=[("Executables", "*.exe"), ("All Files", "*.*")]
		)
		if not filepath:
			return
		self.text_editor.set(str(Path(filepath).resolve()))
	
	def apply_settings(self):
		cfg = ConfigParser()
		
		# save to ini
		cfg["Settings"] = {
			"editor": self.text_editor.get(),
			"scale_factor": self.scale_factor.get()
		}
		
		# reflect on live app
		AppState.text_editor = self.text_editor.get()
		AppState.scale_factor = int(self.scale_factor.get())
		
		if self.old_scale_factor != AppState.scale_factor:
			showinfo("Warning", "Scale factor is changed, click on Reload All\nto apply the new scaling.")
		
		with open (__CONFIG__, "w") as octomap_cfg:
			cfg.write(octomap_cfg)
		return self.destroy()
	
#################################################################################################

class GuessSettings(Toplevel):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.title("Guess settings from project")
		if self.tk.call("tk", "windowingsystem") == "win32":
			self.wm_attributes("-toolwindow", True)
		self.resizable(False, False)
		self.columnconfigure(1, weight=3)
		
		frame = Frame(self, padding="10 10 12 12")
		frame.grid(column=0, row=0, sticky="news")
		
		self.project_directory = StringVar()
		lbl_directory = Label(frame, text="Directory", anchor="e")
		ety_directory = Entry(frame,textvariable=self.project_directory, width=56)
		btn_load = Button(frame, text="Open\u2026", width=6, command=self.open_directory)
		lbl_directory.grid(column=0, row=0, pady=8, padx=4)
		ety_directory.grid(column=1, row=0, sticky="we", padx=4, columnspan=2)
		btn_load.grid(column=3, row=0, sticky="we")
		
		self.status = StringVar()
		self.status.set("Open or type in a directory name")
		lbl_status = Label(frame, textvariable=self.status, anchor="w", relief=SUNKEN, padding="4")
		lbl_status.grid(column=0, row=1, columnspan=4, sticky="we")
		
		sep1 = Separator(frame, orient="horizontal")
		sep1.grid(column=0, row=2, columnspan=4, sticky="we", pady=4)
		
		self.maps_selection = StringVar()
		lbl_map = Label(frame, text="Map", anchor="e")
		self.cbx_map = Combobox(frame, textvariable=self.maps_selection, state="disabled")
		lbl_map.grid(column=0, row=3, sticky="we", pady=4, padx=4)
		self.cbx_map.grid(column=1, row=3, columnspan=3, sticky="we")
		
		lbl_events = Label(frame, text="Events", anchor="e")
		self.events_avail = StringVar()
		self.events_avail.set("Load a map")
		lbl_events_avail = Label(frame, textvariable=self.events_avail, anchor="w", wraplength=400)
		lbl_events.grid(column=0, row=4, sticky="we", pady=4, padx=4)
		lbl_events_avail.grid(column=1, row=4, columnspan=3, sticky="we")
		
		self.sizes_selection = StringVar()
		lbl_sizes = Label(frame, text="Size", anchor="e")
		self.cbx_sizes = Combobox(frame, textvariable=self.sizes_selection, state="disabled")
		lbl_sizes.grid(column=0, row=5, sticky="we", pady=4, padx=4)
		self.cbx_sizes.grid(column=1, row=5, columnspan=3, sticky="we")
		
		self.metatile_selection = StringVar()
		lbl_metatile = Label(frame, text="Metatiles", anchor="e")
		self.cbx_metatile = Combobox(frame, textvariable=self.metatile_selection, state="disabled")
		lbl_metatile.grid(column=0, row=6, sticky="we", pady=4, padx=4)
		self.cbx_metatile.grid(column=1, row=6, columnspan=3, sticky="we")
		
		lbl_tileset = Label(frame, text="Tilesets", anchor="e")
		self.tileset_avail = StringVar()
		self.tileset_avail.set("Load a metatile set")
		lbl_tileset_avail = Label(frame, textvariable=self.tileset_avail, anchor="w", wraplength=400)
		lbl_tileset.grid(column=0, row=7, sticky="we", pady=4, padx=4)
		lbl_tileset_avail.grid(column=1, row=7, columnspan=3, sticky="we")
		
		sep2 = Separator(frame, orient="horizontal")
		sep2.grid(column=0, row=8, columnspan=4, sticky="we", pady=4)
		
		self.initialized = False
		
		btn_cancel = Button(frame, text="Cancel", width=6, command=self.destroy)
		btn_ok = Button(frame, text="OK", width=4, command=self.apply_settings)
		btn_cancel.grid(column=2, row=9, sticky="e", padx=4)
		btn_ok.grid(column=3, row=9, sticky="we")
		
		def reset_all_selections():
			self.events_avail.set("Load a map")
			self.tileset_avail.set("Load a metatile set")
			self.corresponding_asm_file = None
			self.corresponding_tileset_file = None
			self.maps_selection.set("")
			self.sizes_selection.set("")
			self.metatile_selection.set("")
			self.cbx_sizes["values"] = ()
			self.cbx_sizes.configure(state="disabled")

		def init_all_statuses():
			reset_all_selections()
			
			# disable map combobox
			self.cbx_map["values"] = ()
			self.cbx_map.configure(state="disabled")
			
			# disable map size combobox
			self.cbx_sizes["values"] = ()
			self.cbx_sizes.configure(state="disabled")
			
			# disable metatiles combobox
			self.cbx_metatile["values"] = ()
			self.cbx_metatile.configure(state="disabled")
		
		init_all_statuses()
		
		# bind to directory input
		self.all_dirs = {}
		
		def on_project_directory_change(*args):
			basedir = Path(self.project_directory.get())
			self.all_dirs = {
				"metatile": basedir / "data" / "tilesets",
				"gfx": basedir / "gfx" / "tilesets",
				"block": basedir / "maps"
			}
			enable_all = False
			status_lines = []
			counter = 0
			for k, v in self.all_dirs.items():
				available = v.is_dir()
				if available:
					counter += 1
					status_lines.append("%s OK!" % v)
				else:
					status_lines.append("%s MISSING" % v)
				enable_all = counter == len(self.all_dirs.items())
			self.status.set("\n".join(status_lines))
			
			if enable_all:
				reset_all_selections()
				
				# find maps
				self.cbx_map.configure(state="readonly") # enable cbx
				values = []
				for i in self.all_dirs["block"].glob("*.blk"):
					values.append(i.stem)
				self.cbx_map["values"] = tuple(values)
				
				# find metatiles
				self.cbx_metatile.configure(state="readonly") # enable cbx
				values = []
				for i in self.all_dirs["metatile"].glob("*.bin"):
					values.append(re.sub(r"_metatiles$", "", i.stem))
				self.cbx_metatile["values"] = tuple(values)
			else:
				init_all_statuses()
		
		self.project_directory.trace("w", on_project_directory_change)
		
		# bind to maps combobox
		def on_map_combobox_selected(event):
			self.cbx_map.selection_clear()
			self.corresponding_asm_file = self.all_dirs["block"] / (self.maps_selection.get() + ".asm")
			if (self.corresponding_asm_file.is_file()):
				self.events_avail.set("will be loaded from %s" %  self.corresponding_asm_file)
			else:
				self.events_avail.set("can't be loaded automatically")
				self.corresponding_asm_file = None
			
			self.cbx_sizes.configure(state="readonly") # enable cbx
			values = []
			# calculate map sizes
			with open(
				str((self.all_dirs["block"] / (self.maps_selection.get() + ".blk")).resolve()),
				"rb"
			) as map_file:
				map_size = len(map_file.read())
				w = map_size
				while w >= 1:
					h = int(map_size//w)
					if (1 <= w and w <= 255 and 1 <= h and h <= 255 and w*h == map_size):
						# add map sizes
						values.append("%d x %d" % (w, h))
					w -= 1
			self.cbx_sizes["values"] = tuple(values)
			
		self.cbx_map.bind("<<ComboboxSelected>>", on_map_combobox_selected)
		
		# bind to metatiles combo box
		def on_tiles_combobox_selected(event):
			self.cbx_metatile.selection_clear()
			self.corresponding_tileset_file = self.all_dirs["gfx"] / (self.metatile_selection.get() + ".png")
			if (self.corresponding_tileset_file.is_file()):
				self.tileset_avail.set("will be loaded from %s" %  self.corresponding_tileset_file)
			else:
				self.tileset_avail.set("can't be loaded automatically")
				self.corresponding_tileset_file = None
		
		self.cbx_metatile.bind("<<ComboboxSelected>>", on_tiles_combobox_selected)

	def open_directory(self):
		new_directory = askdirectory()
		if new_directory:
			self.project_directory.set(new_directory)
		
	def apply_settings(self):
		# load map block
		if not self.maps_selection.get():
			showerror("Map not selected", "Please select a map")
			return
		AppState.loaded_block_file = str(
			(self.all_dirs["block"] / (self.maps_selection.get() + ".blk")).resolve()
		)
		# load map size
		if not self.sizes_selection.get():
			showerror("Map size not selected", "Please select the map size to use")
			return
		AppState.block_size = tuple(
			[int(i.strip()) for i in self.sizes_selection.get().split(" x ")] 
		)
		# load metatile file
		if not self.metatile_selection.get():
			showerror("Metatile set not selected", "Please select a metatile set")
			return
		AppState.loaded_metatile_file = str(
			(self.all_dirs["metatile"] / (self.metatile_selection.get() + "_metatiles.bin")).resolve()
		)
		# load gfx file
		if not self.corresponding_tileset_file:
			showinfo(
				"No matching GFX",
				"There are no matching graphics file detected for the selected metatiles.\n"
				"You'll need to supply this manually through GFX -> Open."
			)
		else:
			AppState.loaded_tile_file = self.corresponding_tileset_file.resolve()
		# load event file
		if not self.corresponding_asm_file:
			showinfo(
				"No matching events",
				"There are no matching events file detected for the selected layout.\n\n"
				"This may be caused by the layout being shared across different maps, thus\n"
				"there can be many possible events for this map.\n\n"
				"You'll need to supply this manually through Events -> Open."
			)
		else:
			AppState.loaded_event_file = str(self.corresponding_asm_file.resolve())
		self.initialized = True
		return self.destroy()
	
	def show(self):
		self.grab_set()
		self.deiconify()
		self.wait_window()
		return self.initialized

#################################################################################################

class MapPalette(Frame):
	def __init__(self, parent):
		Frame.__init__(self, parent)
		self.parent = parent
		
		self.grid_rowconfigure(1,weight=1)
		self.grid_columnconfigure(1,weight=1)
		
		self.map_area = Canvas(self, width=8*2*AppState.scale_factor, bg="white")
		
		self.max_x = None
		self.max_y = None
		
		ma_hbar = Scrollbar(
			self,
			orient=HORIZONTAL,
			command=self.map_area.xview
		)
		ma_vbar = Scrollbar(
			self,
			orient=VERTICAL,
			command=self.map_area.yview
		)
		
		ma_hbar.grid(row=2,column=1,sticky="ew")
		ma_vbar.grid(row=1,column=2,sticky="ns")
		
		self.map_area.config(
			xscrollcommand=ma_hbar.set,
			yscrollcommand=ma_vbar.set,
		)
		
		self.map_area.grid(row=1,column=1,sticky="news")
		self.status = StringVar()
		self.sbar = Label(self, anchor='w', textvariable=self.status, relief=SUNKEN)
		self.sbar.grid(row=3, column=1, sticky="ew", columnspan=2)
		
		self.title = Label(self, text="Available metatiles", width=8*2*AppState.scale_factor,)
		self.title.grid(row=0, column=1, sticky="ew", columnspan=2)
		self.map_area.bind("<Motion>", self.hover)
		
		self.map_area.bind("<ButtonPress-1>", self.select_metatile)
	
	def hover(self, event):
		if self.max_x is None:
			return
		if self.max_y is None:
			return
		raw_x = ((self.map_area.xview()[0]*self.max_x) + event.x)
		raw_y = ((self.map_area.yview()[0]*self.max_y) + event.y)
		self.status.set(
			"meta 0x%02x, selected 0x%02x" % (
				canvas2block_coord(raw_x) +
				(canvas2block_coord(raw_y)*3),
				AppState.which_metatile
			)
		)
	
	def select_metatile(self, event):
		if self.max_x is None:
			return
		if self.max_y is None:
			return
		raw_x = ((self.map_area.xview()[0]*self.max_x) + event.x)
		raw_y = ((self.map_area.yview()[0]*self.max_y) + event.y)
		AppState.which_metatile = (
			canvas2block_coord(raw_x) +
			(canvas2block_coord(raw_y)*3)
		)
	
	def update_palette(self):
		rendered_tiles = 0
		map_w = 3
		map_h = math.ceil(len(AppState.metatile_readout) / 3)
		
		# save images inside the parent widget, this will also be used by the map view
		self.parent.images = [
			ImageTk.PhotoImage( i.resize((8*AppState.scale_factor, 8*AppState.scale_factor), 0) )
			for i in AppState.tile_images
		]
		
		self.map_area.delete("all")
		
		for y in range(map_h):
			for x in range(map_w):
				# draw tiles as needed only
				if rendered_tiles < len(AppState.metatile_readout):
					cell_index = (3*y)+x
					for h in range(4):
						for w in range(4):
							img_index = (h*4)+w
							#print(img_index)
							self.map_area.create_image(
								((x*8*4)+(w*8))*AppState.scale_factor,
								((y*8*4)+(h*8))*AppState.scale_factor,
								anchor=NW,
								image=self.parent.images[
									AppState.metatile_readout[cell_index][img_index]
								]
							)
				
					self.map_area.create_rectangle(
						block2canvas_coord(x),
						block2canvas_coord(y),
						block2canvas_coord(x+1),
						block2canvas_coord(y+1),
						fill=""
					)
					
					rendered_tiles += 1
		self.max_y = block2canvas_coord(map_h)
		self.max_x = block2canvas_coord(map_w)
		self.map_area.config(
			scrollregion=(0,0,self.max_x,self.max_y)
		)

#################################################################################################

class MapView(Frame):
	def calculate_viewport_location(self, x, y):
		return (
			((self.map_area.xview()[0]*self.max_x) + x),
			((self.map_area.yview()[0]*self.max_y) + y)
		)
	
	def __init__(self, parent):
		Frame.__init__(self, parent)
		self.parent = parent
		
		self.grid_rowconfigure(1,weight=1)
		self.grid_columnconfigure(1,weight=1)
		
		self.map_area = Canvas(self, bg="white")
		
		ma_hbar = Scrollbar(
			self,
			orient=HORIZONTAL,
			command=self.map_area.xview
		)
		ma_vbar = Scrollbar(
			self,
			orient=VERTICAL,
			command=self.map_area.yview
		)
		
		ma_hbar.grid(row=2,column=1,sticky="ew")
		ma_vbar.grid(row=1,column=2,sticky="ns")
		
		self.map_area.config(
			xscrollcommand=ma_hbar.set,
			yscrollcommand=ma_vbar.set,
		)
		
		self.map_area.grid(row=1,column=1,sticky="news")
		self.status = StringVar()
		self.title = Label(self, text="Map block layout")
		self.title.grid(row=0, column=1, sticky="ew", columnspan=2)
		self.sbar = Label(self, anchor='w', textvariable=self.status, relief=SUNKEN)
		self.sbar.grid(row=3, column=1, sticky="ew", columnspan=2)
		
		# update the status bar when the mouse moves in the map
		self.map_area.bind("<Motion>", self.hover)
		
		# register drag event bindings
		for event_type in ["event", "warp", "coord", "bg"]:
			self.map_area.tag_bind(event_type, "<B1-Motion>", self.drag_event)
			self.map_area.tag_bind(event_type, "<ButtonPress-1>", self.drag_event_start)
			self.map_area.tag_bind(event_type, "<ButtonRelease-1>", self.drag_event_end)
			self.map_area.tag_bind(event_type, "<ButtonPress-3>", self.show_event_menu) # right click
			self.map_area.tag_bind(event_type, "<Double-Button-1>", self.edit_event_here_from_menu)
		
		# register block bindings
		self.map_area.tag_bind("block", "<ButtonPress-3>", self.block_eyedrop)
		self.map_area.tag_bind("block", "<ButtonPress-1>", self.block_paint_over)
		self.map_area.tag_bind("block", "<B1-Motion>", self.block_paint_over)
		
		# init stuff
		self.max_x = None
		self.max_y = None
		
		# init drag vars
		self._drag = {"x": 0, "y": 0, "item": None}
	
	def block_eyedrop(self, event):
		# get position
		raw_x, raw_y = self.calculate_viewport_location(event.x, event.y)
		block_x, block_y = (
			canvas2block_coord(raw_x),
			canvas2block_coord(raw_y)
		)
		if (block_y < len(AppState.block_readout)):
			x_len = len(AppState.block_readout[block_y])
			if (block_x < x_len):
				# get which tile
				AppState.which_metatile = AppState.block_readout[block_y][block_x]
		
	def block_paint_over(self, event):
		# apply the metatile
		raw_x, raw_y = self.calculate_viewport_location(event.x, event.y)
		block_x, block_y = (
			canvas2block_coord(raw_x),
			canvas2block_coord(raw_y)
		)
		if (block_y < len(AppState.block_readout)):
			x_len = len(AppState.block_readout[block_y])
			if (block_x < x_len):
				# replace metatile
				AppState.block_readout[block_y][block_x] = AppState.which_metatile
		self.update_map()
	
	def save_events(self):
		for event_type in ["event", "warp", "coord", "bg"]:
			instance_counter = 0
			for event_instance in self.map_area.find_withtag(event_type):
				x1, y1, x2, y2 = self.map_area.coords(event_instance)
				AppState.loaded_events[event_type][instance_counter][0] = str(canvas2event_coord(x1))
				AppState.loaded_events[event_type][instance_counter][1] = str(canvas2event_coord(y1))
				instance_counter += 1
		
	def drag_event_start(self, event):
		raw_x, raw_y = self.calculate_viewport_location(event.x, event.y)
		self._drag = {"x": raw_x, "y": raw_y, "item": self.map_area.find_closest(raw_x, raw_y)[0]}
	
	def drag_event(self, event):
		raw_x, raw_y = self.calculate_viewport_location(event.x, event.y)
		dx = raw_x - self._drag["x"]
		dy = raw_y - self._drag["y"]
		# snap to event coords
		if (dx % (8*2*AppState.scale_factor) == 0):
			self.map_area.move(self._drag["item"], dx, 0)
			self._drag["x"] = raw_x
		if (dy % (8*2*AppState.scale_factor) == 0):
			self.map_area.move(self._drag["item"], 0, dy)
			self._drag["y"] = raw_y
	
	def drag_event_end(self, event):
		self._drag = {"x": 0, "y": 0, "item": None}
		self.save_events()
	
	def show_event_menu(self, event):
		raw_x, raw_y = self.calculate_viewport_location(event.x, event.y)
		object = self.map_area.find_closest(raw_x, raw_y)[0] 
		tags = self.map_area.gettags(object)
		coords = self.map_area.coords(object)
		
		# ensure that what we clicked on isn't a block
		if tags[0] == "block":
			return
		
		m = Menu(self.map_area, tearoff=0)
		m.add_command(label="Show info", command=self.show_event_info(tags))
		m.add_command(label="Show code", command=self.show_event_code(tags, coords))
		m.add_command(label="Toggle visibility", command=self.toggle_event_visibility(tags))
		m.add_command(label="Delete", command=self.delete_event(tags))
		m.add_command(label="Edit...", command=self.edit_event_here(tags))
		m.add_command(label="Open in text editor...", command=self.edit_event_in_editor(tags))
		m.tk_popup(event.x_root, event.y_root)
		m.grab_release()
	
	def show_event_code(self, tags, coords):
		def _():
			if tags[0] == "event":
				command_name = "object_event"
			elif tags[0] == "warp":
				command_name = "warp_event"
			elif tags[0] == "coord":
				command_name = "coord_event"
			elif tags[0] == "bg":
				command_name = "bg_event"
			
			ScrolledInfoWindow(
				self,
				title="%s #%02d (ctrl+a, ctrl+c to copy)" % (tags[0], int(tags[1])),
				text="%s%s %3d, %3d, %s" % (
					"; " if AppState.loaded_events[tags[0]][int(tags[1])][4] else "",
					command_name,
					canvas2event_coord(coords[0]),
					canvas2event_coord(coords[1]),
					AppState.loaded_events[tags[0]][int(tags[1])][2],
				)
			)
		return _
	
	def show_event_info(self, tags):
		def _():
			event_type = tags[0]
			event_num = int(tags[1])
			event_x, event_y = (
				int(AppState.loaded_events[event_type][event_num][0]),
				int(AppState.loaded_events[event_type][event_num][1]),
			)
			event_append = re.sub(r";.+$","",AppState.loaded_events[event_type][event_num][2])
			event_args = [i.strip() for i in event_append.split(",")]
			#print(event_args)
			text = "%s no.%02d\nline: %d\nx: %02d\ny: %02d\nappend: %s\n%s" % (
				event_type,
				event_num,
				AppState.loaded_events[event_type][event_num][3],
				event_x, event_y,
				event_append,
				"NOT visible" if AppState.loaded_events[event_type][event_num][4] else "visible",
			)
			if True: # we're getting macro-specific
				if event_type == "event":
					text = "%s no.%02d\nline: %d\nx: %02d\ny: %02d\nsprite: %s\nmove func: %s\nradii (x, y): (%s, %s)\nhours: [%s, %s]\ncolor: %s\nobject type: %s\nsight range: %s tiles\nscript: %s\n%s\n%s" % (
						event_type,
						event_num,
						AppState.loaded_events[event_type][event_num][3],
						event_x, event_y,
						event_args[0],
						event_args[1],
						event_args[2],
						event_args[3],
						event_args[4],
						event_args[5],
						event_args[6],
						event_args[7],
						event_args[8],
						event_args[9],
						"NEVER disappears" if event_args[10] == "-1" else "disappears when %s is set" % event_args[10],
						"NOT visible" if AppState.loaded_events[event_type][event_num][4] else "visible",
					)
			showinfo(
				"Event info",
				text
			)
		return _
	
	def edit_event_in_editor_from_menu(self, event):
		raw_x, raw_y = self.calculate_viewport_location(event.x, event.y)
		object = self.map_area.find_closest(raw_x, raw_y)[0] 
		tags = self.map_area.gettags(object)
		return self.edit_event_in_editor(tags)()
	
	def edit_event_here_from_menu(self, event):
		raw_x, raw_y = self.calculate_viewport_location(event.x, event.y)
		object = self.map_area.find_closest(raw_x, raw_y)[0] 
		tags = self.map_area.gettags(object)
		return self.edit_event_here(tags)()
	
	def edit_event_here(self, tags):
		def _():
			edited = EditEventDialog(self, tags=tags).show()
			if edited:
				self.update_events()
		return _
	
	def edit_event_in_editor(self, tags):
		def _():
			command = [
				str(Path(AppState.text_editor).resolve()),
				str(Path(AppState.loaded_event_file).resolve()) + (":%d" % AppState.loaded_events[tags[0]][int(tags[1])][3])
			]
			#print(command)
			subprocess.Popen(command, shell=True)
		return _
		
	def delete_event(self, tags):
		def _():
			if askyesno("Delete event", "Really delete this event?"):
				event_type = tags[0]
				event_num = int(tags[1])
				AppState.loaded_events[event_type].pop(event_num)
				self.update_events()
		return _
	
	def toggle_event_visibility(self, tags):
		def _():
			event_type = tags[0]
			event_num = int(tags[1])
			AppState.loaded_events[event_type][event_num][4] = not AppState.loaded_events[event_type][event_num][4]
			self.update_events()
		return _
	
	def update_blocks(self):
		self.map_area.delete("block")
		self.map_area.delete("outline")
		map_w, map_h = AppState.block_size
		# draw map
		for y in range(map_h):
			for x in range(map_w):
				metatile_index = AppState.block_readout[y][x]
				
				for h in range(4):
					for w in range(4):
						img_index = (h*4)+w
						self.map_area.create_image(
							((x*8*4)+(w*8))*AppState.scale_factor,
							((y*8*4)+(h*8))*AppState.scale_factor,
							anchor=NW,
							image=self.parent.images[
								AppState.metatile_readout[metatile_index][img_index]
							],
							tags="block",
						)
				# draw the outlines
				self.map_area.create_rectangle(
					block2canvas_coord(x),
					block2canvas_coord(y),
					block2canvas_coord(x+1),
					block2canvas_coord(y+1),
					fill="",
					outline="black",
					tags="outline",
				)
		self.max_y = block2canvas_coord(map_h)
		self.max_x = block2canvas_coord(map_w)
		self.map_area.config(
			scrollregion=(0,0,self.max_x,self.max_y)
		)
		# reorder stuff
		self.map_area.tag_lower("outline", "all_events")
		self.map_area.tag_lower("block", "outline")
	
	def update_events(self):
		event_type_counters = {
			"event": 0,
			"warp": 0,
			"coord": 0,
			"bg": 0
		}
		event_colors = {
			"event": "blue",
			"warp": "purple",
			"coord": "green",
			"bg": "red"
		}
		
		for event_type in ["event", "warp", "coord", "bg"]:
			self.map_area.delete(event_type)
			for event in AppState.loaded_events[event_type]:
				# defaults
				outline_width = 1
				outline = "black"
				fill = event_colors[event_type]
				
				if event[4]: # if it's commented out, change its look
					fill = ""
					outline = event_colors[event_type]
					outline_width=4
				
				x = int(event[0])
				y = int(event[1])
				ev = self.map_area.create_rectangle(
					event2canvas_coord(x),
					event2canvas_coord(y),
					event2canvas_coord(x+1),
					event2canvas_coord(y+1),
					fill=fill,
					outline=outline,
					width=outline_width,
					tags=(event_type, event_type_counters[event_type], "all_events")
				)
				
				# create tooltip
				ev_ttp = CanvasTooltip(self.map_area, ev, text='\n'.join([i.strip() for i in event[2].split(',')]))
				
				event_type_counters[event_type] += 1
	
	def update_map(self):
		self.map_area.delete("all")
		self.update_events()
		self.update_blocks()
		
	def hover(self, event):
		if self.max_x is None:
			return
		if self.max_y is None:
			return
		raw_x, raw_y = self.calculate_viewport_location(event.x, event.y)
		#print(
		#	self.map_area.gettags(
		#		self.map_area.find_closest(raw_x, raw_y)[0]
		#	)
		#)
		try:
			metatile_num = (
				AppState.block_readout
				[canvas2block_coord(raw_y)]
				[canvas2block_coord(raw_x)]
			)
		except:
			metatile_num = 0xff
		self.status.set(
			"block (%02d, %02d), event (%02d, %02d), meta 0x%02x" % (
				canvas2block_coord(raw_x),
				canvas2block_coord(raw_y),
				canvas2event_coord(raw_x),
				canvas2event_coord(raw_y),
				metatile_num
			)
		)

#################################################################################################

class EditEventDialog(Toplevel):
	def __init__(self, parent=None, tags=None):
		super().__init__(parent)
		self.title("Edit event")
		if self.tk.call("tk", "windowingsystem") == "win32":
			self.wm_attributes("-toolwindow", True)
		self.resizable(False, False)
		self.grab_set()
		
		self.event_type = tags[0]
		self.event_num = int(tags[1])
		
		self.frm_main = Frame(self)
		self.lbl_event_code = Label(self.frm_main)
		self.lbl_event_code.configure(anchor="w", text='Event code')
		self.lbl_event_code.grid(column=0, padx=4, pady=4, row=0, sticky="ew")
		self.visible_checkbox = Checkbutton(self.frm_main)
		self.event_is_visible = BooleanVar(
			value=not AppState.loaded_events[self.event_type][self.event_num][4]
		)
		self.visible_checkbox.configure(
			text='Make visible',
			variable=self.event_is_visible
		)
		self.visible_checkbox.grid(
			column=0, columnspan=3, padx=4, pady=4, row=2)
		self.event_code = ScrolledText(self.frm_main)
		self.event_code.configure(height=3, width=50)
		self.event_code.grid(
			column=0,
			columnspan=2,
			padx=4,
			pady=4,
			row=1,
			sticky="ew")
		self.button_holder = Frame(self.frm_main)
		
		self.btn_ok = Button(self.button_holder, text="OK", command=self.do_btn_ok)
		self.btn_cancel = Button(self.button_holder, text="Cancel", command=self.do_btn_cancel)
		
		self.btn_cancel.pack(padx=4, pady=4, side="right")
		self.btn_ok.pack(padx=4, pady=4, side="right")

		self.button_holder.grid(column=0, columnspan=3, row=3, sticky="ew")
		self.frm_main.pack(ipadx=4, ipady=4, side="top")
		
		# populate event code
		self.event_code.insert('1.0', AppState.loaded_events[self.event_type][self.event_num][2])
		
		self.event_is_changed = False
	
	def do_btn_cancel(self):
		self.destroy()
	
	def do_btn_ok(self):
		self.event_is_changed = True
		AppState.loaded_events[self.event_type][self.event_num][4] = not(bool(self.event_is_visible.get()))
		AppState.loaded_events[self.event_type][self.event_num][2] = self.event_code.get('1.0', 'end').strip()
		self.destroy()
		
	def show(self):
		self.deiconify()
		self.wait_window()
		return self.event_is_changed
	
	

#################################################################################################

if __name__ == "__main__":
	app = App()
	app.mainloop()
