import tkinter as tk
from tkinter import filedialog, colorchooser, ttk
from PIL import Image, ImageTk
import math
import csv

class AnnotatorApp(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.pack(fill=tk.BOTH, expand=True)

        self.image = None # 読み込み画像
        #self.image = Image.open(image_path) # 読み込み画像
        self.scale = 1.0 # 画像拡大率
        self.annotations = [] # 座標情報
        self.undo_stack = [] # 取り消し処理用スタック
        self.redo_stack = [] # 取り消し処理再実行用スタック
        self.next_id = 1 # 次描画する四角形のid
        self.rect_preview = None # 描画中四角形格納用
        self.start_x = self.start_y = 0 # 四角形描画開始位置
        self.number_color = 'blue' # 四角形内数字描画色
        self.square_color = 'yellowgreen' # 四角形枠描画色
        self.modify_ann = None # 調整中四角形の座標情報保持用

        self.build_ui() # UI作成
        #self.new_image()
        self.update_image() # 描画更新


    # 初期UI作成
    def build_ui(self):

        # メニューバー
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)
        
        # ファイルメニュー
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='ファイル', menu=file_menu)
        file_menu.add_command(label='ファイルを開く', command=self.new_image)
        file_menu.add_separator()
        file_menu.add_command(label='CSV Export', command=self.export_csv)
        file_menu.add_command(label='CSV Import', command=self.import_csv)

        # 色設定メニュー
        color_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='色設定', menu=color_menu)
        color_menu.add_command(label='描画する番号', command=self.number_set_color)
        color_menu.add_command(label='描画する枠線', command=self.square_set_color)

        # 画面の左右分割
        self.left_frame = tk.Frame(self)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.right_frame = tk.Frame(self, width=300)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=3)
        self.right_frame.pack_propagate(False)

        # 画像表示 (Canvas)
        self.canvas = tk.Canvas(self.left_frame, bg='gray')
        self.hbar = tk.Scrollbar(self.left_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.vbar = tk.Scrollbar(self.left_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.config(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 座標情報リスト表示 (Treeview)
        self.tree = ttk.Treeview(self.right_frame, columns=("ID", "Name", "X1", "Y1", "X2", "Y2"), show='headings')
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
        # 各列の幅を設定
        self.tree.column("ID", width=40, anchor="center")
        self.tree.column("Name", width=100, anchor="w")
        self.tree.column("X1", width=40, anchor="center")
        self.tree.column("Y1", width=40, anchor="center")
        self.tree.column("X2", width=40, anchor="center")
        self.tree.column("Y2", width=40, anchor="center")    
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # 座標情報編集用エリア
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
        self.delete_btn = tk.Button(self.edit_frame, text="Delete", command=self.delete_annotation_from_ui)
        self.delete_btn.pack(fill=tk.X)

        # イベント設定
        self.canvas.bind("<MouseWheel>", self.zoom)
        self.canvas.bind("<ButtonPress-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.update_draw)
        self.canvas.bind("<ButtonRelease-1>", self.finish_draw)
        self.master.bind("<Control-z>", self.undo)
        self.master.bind("<Control-y>", self.redo)

    # 描画更新
    def update_image(self):     
        # 画像を読み込んでいない場合、処理を行わない
        if not self.image:
            return

        # 読み込み画像の拡縮
        w, h = self.image.size
        resized = self.image.resize((int(w * self.scale), int(h * self.scale)), Image.LANCZOS)
        self.tkimage = ImageTk.PhotoImage(resized)

        # キャンバスのリセット、拡縮後画像表示
        self.canvas.delete("all")
        self.img_id = self.canvas.create_image(0, 0, anchor='nw', image=self.tkimage)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

        # 四角形の描画
        for ann in self.annotations:
            self.draw_annotation(ann)
        self.refresh_tree() # 座標情報リストの更新
    
    # 四角形描画
    def draw_annotation(self, ann):
        # 座標取得後、拡縮率分変換し、四角形を描画
        x1, y1, x2, y2 = ann['image_coords']
        canvas_coords = [coord * self.scale for coord in (x1, y1, x2, y2)]
        rect_id = self.canvas.create_rectangle(*canvas_coords, width=2, outline=self.square_color)
        
        # 四角形の中に描画番号を描画
        text_x = (canvas_coords[0] + canvas_coords[2]) / 2
        text_y = (canvas_coords[1] + canvas_coords[3]) / 2
        text_id = self.canvas.create_text(text_x, text_y, text=str(ann['id']), fill=self.number_color,  font=("Arial", 12))

        # キャンバス上での識別番号をデータに追加
        ann['rect_id'] = rect_id
        ann['text_id'] = text_id

    # リスト表示の更新
    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children()) # 既存のデータを削除

        # 現在の座標情報を追加し、データを表示
        for ann in self.annotations:
            x1, y1, x2, y2 = ann['image_coords']
            self.tree.insert("", "end", iid=str(ann['id']), values=(ann['id'], ann.get('name',''), x1, y1, x2, y2))
    
    # リスト表示選択時
    def on_select(self, event):       
        selected = self.tree.selection() # 選択されているアイテムを取得

        # 選択されていたら
        if selected:           
            # 選択されているアイテムのidの座標情報を取得
            iid = int(selected[0])
            ann = next((a for a in self.annotations if a['id'] == iid), None)

            # 座標情報が存在する場合、そのデータを編集エリアに表示
            if ann:
                self.name_entry.delete(0, tk.END)
                self.name_entry.insert(0, ann.get('name',''))
                x1, y1, x2, y2 = ann['image_coords']
                self.coord_entry.delete(0, tk.END)
                self.coord_entry.insert(0, f"{x1},{y1},{x2},{y2}")

    # 座標情報更新処理
    def update_annotation_from_ui(self):
        selected = self.tree.selection() # 選択されているアイテムを取得
        
        # 選択されているアイテムがある場合
        if selected:
            # 選択されているアイテムのidを取得
            iid = int(selected[0])
            ann = next((a for a in self.annotations if a['id'] == iid), None)

            # 選択されているアイテムのidが座標情報リストに存在する場合
            if ann:
                # 入力されている座標を取得
                old_ann = ann.copy()
                name = self.name_entry.get()
                coords = tuple(map(int, self.coord_entry.get().split(',')))

                # 左下座標、右上座標に整理
                x1, y1 = min(coords[0], coords[2]), max(coords[1], coords[3])
                x2, y2 = max(coords[0], coords[2]), min(coords[1], coords[3])

                # 他の四角形と当たっていなければ座標データを更新
                if not self.hit_square(x1, y1, x2, y2, ann['id']) :
                    ann['name'] = name
                    ann['image_coords'] = (x1, y1, x2, y2)
                    self.undo_stack.append(('edit', old_ann))
                    self.redo_stack.clear()
                    self.update_image()                




    # 座標情報削除処理
    def delete_annotation_from_ui(self):
        selected = self.tree.selection() # 選択されているアイテムを取得

        # 選択されているアイテムがある場合
        if selected:
            # 選択されているアイテムのidを取得
            iid = int(selected[0])
            ann = next((a for a in self.annotations if a['id'] == iid), None)   

            # 選択されているアイテムのidが座標情報リストに存在する場合
            if ann:
                # そのデータを削除する
                self.annotations.remove(ann)
                for a in self.annotations :
                    if a['id'] > iid :
                        a['id'] -= 1
                self.undo_stack.append(('delete', ann))
                self.redo_stack.clear()
                self.update_image()
                self.next_id -= 1         

    # 拡縮処理
    def zoom(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        if event.delta > 0:
            self.scale *= 1.1
        else:
            self.scale /= 1.1
        self.update_image()
        #self.canvas.xview_moveto(cx / self.tkimage.width())
        #self.canvas.yview_moveto(cy / self.tkimage.height())
    
    # 四角形描画開始
    def start_draw(self, event):
        # 画像を読み込んでいない場合、処理を行わない
        if not self.image:
            return

        # キャンバス上でのクリックした座標を取得    
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)

        # 既存の描画中四角形がある場合はキャンバス上から削除
        if self.rect_preview:
            self.canvas.delete(self.rect_preview)

        # 既存の四角形内をクリックしたか判定
        is_hit, coord, ann = self.hit_vertex(int(self.start_x / self.scale), int(self.start_y / self.scale)) 

        # 四角形内をクリックしていた場合
        if (is_hit) :
            # クリックした四角形をキャンバス上から削除
            self.canvas.delete(ann['rect_id'])
            self.canvas.delete(ann['text_id'])
            # クリックした四角形の座標情報番号を保持した後、クリックした四角形の調整を開始
            self.modify_ann = ann
            end_x = self.start_x
            end_y = self.start_y
            self.start_x = coord[0] * self.scale
            self.start_y = coord[1] * self.scale
            self.rect_preview = self.canvas.create_rectangle(self.start_x, self.start_y, end_x, end_y, width=2, outline=self.square_color)
        # 通常の描画開始
        else:
            self.rect_preview = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, width=2, outline=self.square_color)

    # 四角形描画中
    def update_draw(self, event):
        # 画像を読み込んでいない場合、処理を行わない
        if not self.image:
            return

        # 描画中の四角形を現在のマウス位置を元にサイズ変更    
        curr_x = self.canvas.canvasx(event.x)
        curr_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect_preview, self.start_x, self.start_y, curr_x, curr_y)

    # 四角形描画終了
    def finish_draw(self, event):
        # 画像を読み込んでいない場合、処理を行わない
        if not self.image:
            return
        # 描画中の四角形があれば    
        if self.rect_preview:
            # ドラッグ終了時座標取得
            end_x = self.canvas.canvasx(event.x)
            end_y = self.canvas.canvasy(event.y)
            # 左下座標、右上座標を拡縮分変換して取得
            x1, y1 = int(min(self.start_x, end_x) / self.scale), int(max(self.start_y, end_y) / self.scale)
            x2, y2 = int(max(self.start_x, end_x) / self.scale), int(min(self.start_y, end_y) / self.scale)
            # 既存四角形の調整操作の場合、調整した四角形の既存座標情報を削除
            if self.modify_ann :
                del self.annotations[self.modify_ann['id'] - 1]
            # 既存の座標の四角形と当たっていない四角形の場合、座標情報を追加し描画に反映
            if not self.hit_square(x1, y1, x2, y2) :
                ann = {'id': self.next_id, 'name':'', 'image_coords': (x1, y1, x2, y2)}

                # 既存四角形の調整操作の場合、調整した四角形のidに設定
                if self.modify_ann :
                    ann['id'] = self.modify_ann['id']
                    ann['name'] = self.modify_ann['name']
                    self.annotations.insert(self.modify_ann['id']-1, ann)
                    self.undo_stack.append(('edit', self.modify_ann))
                    self.modify_ann = None # 調整中座標情報をリセット
                # 新規四角形描画    
                else :
                    self.annotations.append(ann)
                    self.undo_stack.append(('add', ann))    
                    self.next_id += 1 

                self.redo_stack.clear()
                self.update_image()

            # 調整中の四角形が、既存の座標の四角形と当たっていた場合    
            elif self.modify_ann :
                self.annotations.insert(self.modify_ann['id']-1 ,self.modify_ann)
                self.modify_ann = None # 調整中座標情報をリセット
                self.update_image()    

            # 描画中の四角形を削除  
            self.canvas.delete(self.rect_preview)
            self.rect_preview = None

            #print(self.annotations)

    # 座標と四角形の当たり判定
    # ax1,ay1 : 左下    ax2,ay2 : 右上
    # 戻り値： 当たり判定、最も遠い頂点座標、当たった四角形の座標情報
    def hit_vertex(self, x1, y1):
        for ann in self.annotations:
            ax1, ay1, ax2, ay2 = ann['image_coords']
            # 当たっていた場合、当たっていた四角形の頂点座標のうち、座標からもっと最も遠い頂点座標を返す
            # 同じ値は当たっていると判断
            if (x1 >= ax1 and x1 <= ax2) and (y1 <= ay1 and y1 >= ay2):
                vertex = (x1, y1)
                square_vertex = [(ax1, ay2), (ax2, ay2), (ax1, ay1), (ax2, ay1)]
                length = self.calculate_distance(vertex, square_vertex[0])
                coord = square_vertex[0]
                for squvtx in square_vertex[1:]:
                    length2 = self.calculate_distance(vertex, squvtx)
                    if (length < length2):
                        length = length2
                        coord = squvtx
                return True, coord, ann
        return False, False, False      

    # 2つのタプル型座標のユークリッド距離を計算            
    def calculate_distance(self, coord1, coord2):
        x1, y1 = coord1
        x2, y2 = coord2
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)            

    # 四角形同士の当たり判定
    # x1,y1 : 左下    x2,y2 : 右上
    # ax1,ay1 : 左下    ax2,ay2 : 右上
    # skip_id：当たり判定を取らない四角形のid
    # 戻り値：当たり判定
    def hit_square(self, x1, y1, x2, y2, skip_id=0):
        for ann in self.annotations:
            # スキップidの四角形とは当たり判定を取らない
            if ann['id'] == skip_id :
                continue

            ax1, ay1, ax2, ay2 = ann['image_coords'] # 座標取得

            # 同じ値は当たっていないと判断
            if (x1 < ax2 and x2 > ax1) and (y1 > ay2 and y2 < ay1):
                return True                
        return False

    
    # 直前の操作取り消し処理
    def undo(self, event=None):
        if not self.undo_stack:
            return
        action, data = self.undo_stack.pop()
        # 座標情報追加操作の取り消し
        if action == 'add':
            ann = data
            self.annotations = [a for a in self.annotations if a['id'] != ann['id']]
            self.next_id -= 1
            self.redo_stack.append(('add', ann))
        # 座標情報修正操作の取り消し    
        elif action == 'edit':
            iid, old_ann = data['id'], data
            current = next((a for a in self.annotations if a['id']==iid), None)
            if current:
                redo_ann = current.copy()
                current.update(old_ann)
                self.redo_stack.append(('edit', redo_ann))
        # 座標情報削除操作の取り消し        
        elif action == 'delete':
            iid, ann = data['id'], data
            for a in self.annotations :
                if a['id'] >= iid :
                    a['id'] += 1
            self.annotations.insert(iid-1, ann)
            self.next_id += 1      
            self.redo_stack.append(('delete', ann))  
        self.update_image()

    # 取り消し処理の再実行
    def redo(self, event=None):
        if not self.redo_stack:
            return
        action, data = self.redo_stack.pop()
        # 取り消した座標情報追加操作の実行
        if action == 'add':
            ann = data
            self.annotations.append(ann)
            self.undo_stack.append(('add', ann))
            self.next_id += 1
        # 取り消した座標情報修正操作の実行    
        elif action == 'edit':
            iid, new_ann = data['id'], data
            current = next((a for a in self.annotations if a['id']==iid), None)
            if current:
                undo_ann = current.copy()
                current.update(new_ann)
                self.undo_stack.append(('edit', undo_ann))
        # 取り消した座標情報削除操作の実行        
        elif action == 'delete':
            iid, ann = data['id'], data
            self.annotations.remove(ann)
            for a in self.annotations :
                if a['id'] > iid :
                    a['id'] -= 1
            self.undo_stack.append(('delete', ann))
            self.next_id -= 1      
        self.update_image()

    # 新規画像読み込み
    def new_image(self):        
        # 画像ファイルの読み込み
        filepath = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.png *.bmp")]) 

        if (filepath):
            self.image = Image.open(filepath) # 読み込み画像の変更

            # パラメータ、既存座標情報のリセット
            self.scale = 1.0
            self.annotations.clear()
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.next_id = 1

            self.update_image() # 更新

            return True
        return False    


    # CSV出力
    def export_csv(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if filename:
            # 書き込みモードでファイルを開く
            with open(filename, "w", newline='') as f:
                writer = csv.writer(f)
                # 座標データの書き込み
                writer.writerow(["id","name","x1","y1","x2","y2"]) # ヘッダー
                for ann in self.annotations:
                    x1, y1, x2, y2 = ann['image_coords']
                    writer.writerow([ann['id'], ann.get('name',''), x1, y1, x2, y2])
            print(f"Exported to {filename}")

    # CSV読み込み
    def import_csv(self):
        filename = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if filename:
            # 読み込みモードでファイルを開く
            with open(filename, "r") as f:
                reader = csv.reader(f)
                # 既存リスト、描画番号のリセット
                self.annotations.clear()
                self.undo_stack.clear()
                self.redo_stack.clear()
                self.next_id = 1

                next(reader) # ヘッダー行をスキップ

                # 座標データの読み込み
                for row in reader:
                    ann = {'id': int(row[0]), 'name':row[1], 'image_coords': tuple(map(int, row[2:]))}
                    self.annotations.append(ann)
                    self.next_id += 1
            self.update_image() # 読み込んだデータを画面表示に反映

    # 番号色設定
    def number_set_color(self):
        # 色選択ダイアログを開く
        color_code = colorchooser.askcolor(title="描画される番号の色を選択")[1]
        if color_code:  # ユーザーが色を選択した場合
            self.number_color = color_code
            self.update_image() # 画面を再描画

    # 枠線色設定
    def square_set_color(self):
        # 色選択ダイアログを開く
        color_code = colorchooser.askcolor(title="描画される枠線の色を選択")[1]
        if color_code:  # ユーザーが色を選択した場合
            self.square_color = color_code   
            self.update_image() # 画面を再描画     


# メイン実行処理
if __name__ == "__main__":

    # メインウィンドウ作成
    root = tk.Tk()

    # ウィンドウの設定
    root.title("Advanced Image Annotator")
    root.geometry("1200x600")

    # 座標取得画面を作成
    app = AnnotatorApp(root)
    app.mainloop()

    # 画像ファイルの読み込み
    #filepath = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.png *.bmp")])

    # 読み込んだ場合、座標取得ウィジェットを作成
    #if filepath:
    #    app = AnnotatorApp(root, filepath) 
    #    app.mainloop()
