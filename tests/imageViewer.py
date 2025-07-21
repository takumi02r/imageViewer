import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk
import csv

class AnnotatorApp(tk.Frame):
    def __init__(self, master, image_path):
        super().__init__(master)
        self.master = master
        self.pack(fill=tk.BOTH, expand=True)

        self.image = Image.open(image_path)
        self.scale = 1.0
        self.annotations = []
        self.undo_stack = []
        self.redo_stack = []
        self.next_id = 1

        self.build_ui()
        self.update_image()

    def build_ui(self):
        # 左右分割
        self.left_frame = tk.Frame(self)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.right_frame = tk.Frame(self, width=300)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_frame.pack_propagate(False)

        # Canvas
        self.canvas = tk.Canvas(self.left_frame, bg='gray')
        self.hbar = tk.Scrollbar(self.left_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.vbar = tk.Scrollbar(self.left_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.config(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # イベント
        self.canvas.bind("<MouseWheel>", self.zoom)
        self.canvas.bind("<ButtonPress-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.update_draw)
        self.canvas.bind("<ButtonRelease-1>", self.finish_draw)
        self.master.bind("<Control-z>", self.undo)
        self.master.bind("<Control-y>", self.redo)

        # Treeview
        self.tree = ttk.Treeview(self.right_frame, columns=("ID", "Name", "X1", "Y1", "X2", "Y2"), show='headings')
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
        # ID列を狭く、名前を少し広く
        self.tree.column("ID", width=20, anchor="center")
        self.tree.column("Name", width=50, anchor="w")
        self.tree.column("X1", width=20, anchor="center")
        self.tree.column("Y1", width=20, anchor="center")
        self.tree.column("X2", width=20, anchor="center")
        self.tree.column("Y2", width=20, anchor="center")    
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # 編集用エリア
        self.edit_frame = tk.Frame(self.right_frame)
        self.edit_frame.pack(fill=tk.X)
        tk.Label(self.edit_frame, text="Name").pack()
        self.name_entry = tk.Entry(self.edit_frame)
        self.name_entry.pack(fill=tk.X)
        tk.Label(self.edit_frame, text="X1,Y1,X2,Y2").pack()
        self.coord_entry = tk.Entry(self.edit_frame)
        self.coord_entry.pack(fill=tk.X)
        self.update_btn = tk.Button(self.edit_frame, text="Update", command=self.update_annotation_from_ui)
        self.update_btn.pack(fill=tk.X)

        # CSV
        btn = tk.Button(self.right_frame, text="Export CSV", command=self.export_csv)
        btn.pack(fill=tk.X)

        self.rect_preview = None
        self.start_x = self.start_y = 0

    def update_image(self):
        w, h = self.image.size
        resized = self.image.resize((int(w * self.scale), int(h * self.scale)), Image.LANCZOS)
        self.tkimage = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        self.img_id = self.canvas.create_image(0, 0, anchor='nw', image=self.tkimage)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

        for ann in self.annotations:
            self.draw_annotation(ann)
        self.refresh_tree()

    def draw_annotation(self, ann):
        x1, y1, x2, y2 = ann['image_coords']
        canvas_coords = [coord * self.scale for coord in (x1, y1, x2, y2)]
        rect_id = self.canvas.create_rectangle(*canvas_coords, outline='green')
        text_x = (canvas_coords[0] + canvas_coords[2]) / 2
        text_y = (canvas_coords[1] + canvas_coords[3]) / 2
        text_id = self.canvas.create_text(text_x, text_y, text=str(ann['id']), fill='blue',  font=("Arial", 12))
        ann['rect_id'] = rect_id
        ann['text_id'] = text_id

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for ann in self.annotations:
            x1, y1, x2, y2 = ann['image_coords']
            self.tree.insert("", "end", iid=str(ann['id']), values=(ann['id'], ann.get('name',''), x1, y1, x2, y2))

    def on_select(self, event):
        selected = self.tree.selection()
        if selected:
            iid = int(selected[0])
            ann = next((a for a in self.annotations if a['id'] == iid), None)
            if ann:
                self.name_entry.delete(0, tk.END)
                self.name_entry.insert(0, ann.get('name',''))
                x1, y1, x2, y2 = ann['image_coords']
                self.coord_entry.delete(0, tk.END)
                self.coord_entry.insert(0, f"{x1},{y1},{x2},{y2}")

    def update_annotation_from_ui(self):
        selected = self.tree.selection()
        if selected:
            iid = int(selected[0])
            ann = next((a for a in self.annotations if a['id'] == iid), None)
            if ann:
                old_ann = ann.copy()
                name = self.name_entry.get()
                coords = tuple(map(int, self.coord_entry.get().split(',')))
                ann['name'] = name
                ann['image_coords'] = coords
                self.undo_stack.append(('edit', iid, old_ann))
                self.redo_stack.clear()
                self.update_image()

    def zoom(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        if event.delta > 0:
            self.scale *= 1.1
        else:
            self.scale /= 1.1
        self.update_image()
        self.canvas.xview_moveto((cx * self.scale) / self.tkimage.width())
        self.canvas.yview_moveto((cy * self.scale) / self.tkimage.height())

    def start_draw(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect_preview:
            self.canvas.delete(self.rect_preview)
        self.rect_preview = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='green')

    def update_draw(self, event):
        curr_x = self.canvas.canvasx(event.x)
        curr_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect_preview, self.start_x, self.start_y, curr_x, curr_y)

    def finish_draw(self, event):
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        x1, y1 = min(self.start_x, end_x) / self.scale, max(self.start_y, end_y) / self.scale
        x2, y2 = max(self.start_x, end_x) / self.scale, min(self.start_y, end_y) / self.scale
        ann = {'id': self.next_id, 'name':'', 'image_coords': (int(x1), int(y1), int(x2), int(y2))}
        self.annotations.append(ann)
        self.undo_stack.append(('add', ann))
        self.redo_stack.clear()
        self.update_image()
        self.next_id += 1
        if self.rect_preview:
            self.canvas.delete(self.rect_preview)
            self.rect_preview = None

    def undo(self, event=None):
        if not self.undo_stack:
            return
        action, data = self.undo_stack.pop()
        if action == 'add':
            ann = data
            self.annotations = [a for a in self.annotations if a['id'] != ann['id']]
            self.redo_stack.append(('add', ann))
        elif action == 'edit':
            iid, old_ann = data, data
            current = next((a for a in self.annotations if a['id']==iid), None)
            if current:
                redo_ann = current.copy()
                current.update(old_ann)
                self.redo_stack.append(('edit', iid, redo_ann))
        self.update_image()

    def redo(self, event=None):
        if not self.redo_stack:
            return
        action, data = self.redo_stack.pop()
        if action == 'add':
            ann = data
            self.annotations.append(ann)
            self.undo_stack.append(('add', ann))
        elif action == 'edit':
            iid, new_ann = data, data
            current = next((a for a in self.annotations if a['id']==iid), None)
            if current:
                undo_ann = current.copy()
                current.update(new_ann)
                self.undo_stack.append(('edit', iid, undo_ann))
        self.update_image()

    def export_csv(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if filename:
            with open(filename, "w", newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["id","name","x1","y1","x2","y2"])
                for ann in self.annotations:
                    x1, y1, x2, y2 = ann['image_coords']
                    writer.writerow([ann['id'], ann.get('name',''), x1, y1, x2, y2])
            print(f"Exported to {filename}")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Advanced Image Annotator")
    root.geometry("1200x700")
    filepath = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.png *.bmp")])
    if filepath:
        app = AnnotatorApp(root, filepath)
        app.mainloop()
