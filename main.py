import sys, random, math, subprocess, os, json, socket
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QMenu, QAction
from PyQt5.QtGui import QPixmap, QCursor
from PyQt5.QtCore import Qt, QTimer, QPoint

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
DB_FILE = "stolen_data.json"


try:
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lock_socket.bind(("127.0.0.1", 47200))
except socket.error:
    print("Скрипт запущен")
    sys.exit(0)

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class MarisaUltimate(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.idle_img = QPixmap(get_resource_path('idle.png'))
        self.move_img = QPixmap(get_resource_path('movet.png'))
        
        self.label = QLabel(self)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.update_img(self.idle_img)

        self.state = "WANDERING"
        self.dragging = False
        self.drag_start_pos = QPoint()
        
        self.angle = random.uniform(0, 2 * math.pi)
        self.speed = 3
        
        self.stolen_items = self.load_db()
        self.target_pos = None
        self.current_target_idx = -1

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.game_loop)
        self.timer.start(30)

        self.ai_timer = QTimer(self)
        self.ai_timer.timeout.connect(self.plan_steal)
        self.ai_timer.start(5000)

        self.move(500, 500)

    def load_db(self):
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, 'r') as f:
                    return json.load(f)
            except: return []
        return []

    def save_db(self):
        with open(DB_FILE, 'w') as f:
            json.dump(self.stolen_items, f)

    def update_img(self, pix):
        self.label.setPixmap(pix)
        self.label.adjustSize()
        self.resize(pix.size())

    def call_stealer(self, mode, idx, x=0, y=0):
        exe = get_resource_path('stealer.exe')
        if not os.path.exists(exe): return None
        try:
            res = subprocess.run([exe, mode, str(idx), str(x), str(y)], 
                                 capture_output=True, text=True, 
                                 creationflags=0x08000000, timeout=1)
            if mode == "get":
                p = res.stdout.strip().split()
                if len(p) >= 2: return int(p[0]), int(p[1])
            return True
        except: return None

    def plan_steal(self):
        if self.state == "TARGETING" or self.dragging or len(self.stolen_items) >= 4:
            return
        check_indices = list(range(40))
        random.shuffle(check_indices)
        already_stolen = [item['idx'] for item in self.stolen_items]
        
        for idx in check_indices:
            if idx in already_stolen: continue
            pos = self.call_stealer("get", idx)
            if pos and 0 <= pos[0] < 4000 and 0 <= pos[1] < 3000:
                self.current_target_idx = idx
                self.target_pos = QPoint(pos[0], pos[1])
                self.state = "TARGETING"
                break

    def game_loop(self):
        if self.dragging: return
        cur = self.pos()
        screen = QApplication.primaryScreen().availableGeometry()

        if self.state == "WANDERING":
            if random.random() < 0.03: self.angle += random.uniform(-0.6, 0.6)
            nx, ny = cur.x() + math.cos(self.angle)*self.speed, cur.y() + math.sin(self.angle)*self.speed
            
            hit = False
            if nx < screen.left(): nx = screen.left(); hit = True
            if nx > screen.right() - self.width(): nx = screen.right() - self.width(); hit = True
            if ny < screen.top(): ny = screen.top(); hit = True
            if ny > screen.bottom() - self.height(): ny = screen.bottom() - self.height(); hit = True
            if hit: self.angle = random.uniform(0, 2 * math.pi)
            self.move(int(nx), int(ny))

        elif self.state == "TARGETING" and self.target_pos:
            dx, dy = self.target_pos.x() - cur.x(), self.target_pos.y() - cur.y()
            dist = math.hypot(dx, dy)
            if dist < 12:
                actual = self.call_stealer("get", self.current_target_idx)
                if actual:
                    self.stolen_items.append({'idx': self.current_target_idx, 'x': actual[0], 'y': actual[1]})
                    self.save_db()
                    self.call_stealer("set", self.current_target_idx, -4096, -4096)
                self.state = "WANDERING"
                self.target_pos = None
            else:
                self.move(int(cur.x() + (dx/dist)*5), int(cur.y() + (dy/dist)*5))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_start_pos = event.globalPos() - self.pos()
            self.update_img(self.move_img)
            event.accept()
        elif event.button() == Qt.RightButton:
            self.show_inventory()

    def mouseMoveEvent(self, event):
        if self.dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self.drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.update_img(self.idle_img)
            c = self.pos()
            changed = False
            for item in self.stolen_items[:]:
                if math.hypot(c.x() - item['x'], c.y() - item['y']) < 130:
                    self.call_stealer("set", item['idx'], item['x'], item['y'])
                    self.stolen_items.remove(item)
                    changed = True
            if changed: self.save_db()
            event.accept()

    def show_inventory(self):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: white; border: 1px solid black; }")
        if not self.stolen_items:
            menu.addAction("Карманы пусты...")
        else:
            header = menu.addAction("--- ИНВЕНТАРЬ ---")
            header.setEnabled(False)
            for item in self.stolen_items:
                action = QAction(f"Ярлык №{item['idx']}", self)
                action.setToolTip(f"Координаты: X={item['x']}, Y={item['y']}")
                action.triggered.connect(lambda checked, i=item: self.force_return(i))
                menu.addAction(action)
        menu.exec_(QCursor.pos())

    def force_return(self, item):
        self.call_stealer("set", item['idx'], item['x'], item['y'])
        if item in self.stolen_items:
            self.stolen_items.remove(item)
            self.save_db()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F4 and (event.modifiers() & Qt.AltModifier):
            self.terminate_all()

    def terminate_all(self):

        self.timer.stop()
        self.ai_timer.stop()
        for item in self.stolen_items:
            self.call_stealer("set", item['idx'], item['x'], item['y'])
        self.stolen_items = []
        self.save_db()

        os._exit(0)

    def closeEvent(self, event):
        self.terminate_all()
        event.accept()

if __name__ == '__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    m = MarisaUltimate()
    m.show()
    sys.exit(app.exec_())