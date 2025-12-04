import sys
import serial
import serial.tools.list_ports
import csv
import os
import datetime
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QComboBox, QPushButton, 
                               QTableWidget, QTableWidgetItem, QTextEdit, QMessageBox, 
                               QGroupBox, QHeaderView, QDialog, QFileDialog, QAbstractItemView) 
from PySide6.QtCore import QThread, Signal, Slot, Qt

# ==========================================
# 1. 商品管理模块
# ==========================================
class ProductManager:
    def __init__(self, filename='products.csv'):
        self.filename = filename
        self.products = {} 
        self.load_data()

    def load_data(self):
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, 'w', encoding='utf-8-sig', newline='') as f:
                    csv.writer(f).writerow(['id', 'name', 'price'])
            except Exception as e:
                print(f"初始化文件失败: {e}")
            return

        try:
            with open(self.filename, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                self.products.clear()
                for row in reader:
                    pid = row.get('id', '').strip()
                    if pid:
                        try:
                            price = float(row.get('price', 0))
                        except ValueError:
                            price = 0.0
                        self.products[pid] = {
                            'name': row.get('name', '未知商品'), 
                            'price': price
                        }
            print(f"系统: 已加载 {len(self.products)} 个商品数据")
        except Exception as e:
            print(f"系统: 商品库加载失败 - {e}")

    def save_data(self, new_data_list):
        try:
            with open(self.filename, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'name', 'price']) 
                for item in new_data_list:
                    writer.writerow([item['id'], item['name'], item['price']])
            self.load_data()
            return True
        except Exception as e:
            print(f"保存失败: {e}")
            return False

    def get_info(self, barcode):
        if barcode in self.products:
            return self.products[barcode]['name'], self.products[barcode]['price']
        return "未知商品", 0.0
    
    def get_all_list(self):
        data_list = []
        for pid, info in self.products.items():
            data_list.append({'id': pid, 'name': info['name'], 'price': info['price']})
        return data_list

# ==========================================
# 2. 今日销售统计窗口
# ==========================================
class DailyReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("今日销售结算")
        self.resize(800, 500)
        self.today_records = [] 
        self.init_ui()
        self.load_today_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.lbl_summary = QLabel("正在计算...")
        self.lbl_summary.setStyleSheet("font-size: 18px; font-weight: bold; color: #2196F3; padding: 10px; border: 2px solid #ddd;")
        layout.addWidget(self.lbl_summary)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["时间", "条码", "商品名称", "单价", "数量", "小计金额"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_export = QPushButton("📤 导出今日报表 (CSV)")
        btn_export.setStyleSheet("background-color: #009688; color: white; font-weight: bold; padding: 8px;")
        btn_export.clicked.connect(self.export_csv)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_export)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def load_today_data(self):
        filename = 'sales_record.csv'
        target_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        self.today_records = []
        total_revenue = 0.0
        total_items = 0

        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    for row in reader:
                        if not row: continue
                        record_time = row[0]
                        if record_time.startswith(target_date):
                            try:
                                price = float(row[3])
                                qty = int(row[4])
                                subtotal = price * qty
                                self.today_records.append(row + [f"{subtotal:.2f}"])
                                total_revenue += subtotal
                                total_items += qty
                            except:
                                continue 
            except Exception as e:
                QMessageBox.warning(self, "读取错误", f"无法读取销售记录: {e}")

        self.table.setRowCount(len(self.today_records))
        for i, row_data in enumerate(self.today_records):
            for j, val in enumerate(row_data):
                self.table.setItem(i, j, QTableWidgetItem(str(val)))
        
        self.lbl_summary.setText(f"📅 日期: {target_date}   |   💰 今日总营收: ¥{total_revenue:.2f}   |   📦 售出商品数: {total_items}")

    def export_csv(self):
        if not self.today_records:
            QMessageBox.warning(self, "提示", "今日暂无数据，无需导出。")
            return
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        default_name = f"DailyReport_{today_str}.csv"
        file_path, _ = QFileDialog.getSaveFileName(self, "导出今日报表", default_name, "CSV Files (*.csv)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Time", "Barcode", "Name", "Price", "Quantity", "Subtotal"])
                    writer.writerows(self.today_records)
                QMessageBox.information(self, "成功", f"报表已成功导出至:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "失败", f"导出失败: {e}")

# ==========================================
# 3. [新增] 模拟扫码选择窗口
# ==========================================
class ScanSimulationDialog(QDialog):
    def __init__(self, data_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择要模拟扫描的商品")
        self.resize(600, 400)
        self.data_list = data_list
        self.selected_id = None # 用于存储用户选择的ID
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 提示语
        lbl = QLabel("请从列表中选择一个商品，双击或点击按钮发送：")
        layout.addWidget(lbl)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["条码 (ID)", "商品名称", "价格"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # 设置为只读、整行选择
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        # 双击直接触发选择
        self.table.doubleClicked.connect(self.select_and_accept)
        
        layout.addWidget(self.table)
        self.load_table_data()

        # 按钮
        btn_layout = QHBoxLayout()
        btn_scan = QPushButton("📡 发送模拟扫码")
        btn_scan.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        btn_scan.clicked.connect(self.select_and_accept)
        
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_scan)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def load_table_data(self):
        self.table.setRowCount(len(self.data_list))
        for i, item in enumerate(self.data_list):
            self.table.setItem(i, 0, QTableWidgetItem(str(item['id'])))
            self.table.setItem(i, 1, QTableWidgetItem(str(item['name'])))
            self.table.setItem(i, 2, QTableWidgetItem(str(item['price'])))

    def select_and_accept(self):
        # 获取当前选中的行
        curr_row = self.table.currentRow()
        if curr_row < 0:
            QMessageBox.warning(self, "提示", "请先选择一行商品！")
            return
        
        # 获取ID (第0列)
        self.selected_id = self.table.item(curr_row, 0).text()
        self.accept()

# ==========================================
# 4. 商品编辑窗口 (原)
# ==========================================
class ProductEditorDialog(QDialog):
    def __init__(self, data_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("管理商品信息库")
        self.resize(600, 400)
        self.data_list = data_list
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["条码 (ID)", "商品名称 (Name)", "价格 (Price)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        self.load_table_data()

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 添加一行")
        btn_add.clicked.connect(self.add_row)
        btn_del = QPushButton("➖ 删除选中行")
        btn_del.clicked.connect(self.delete_row)
        btn_save = QPushButton("💾 保存并同步")
        btn_save.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.check_and_save) 
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_del)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def load_table_data(self):
        self.table.setRowCount(len(self.data_list))
        for i, item in enumerate(self.data_list):
            self.table.setItem(i, 0, QTableWidgetItem(str(item['id'])))
            self.table.setItem(i, 1, QTableWidgetItem(str(item['name'])))
            self.table.setItem(i, 2, QTableWidgetItem(str(item['price'])))

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.setItem(row, 2, QTableWidgetItem("0.00"))
        self.table.scrollToBottom()

    def delete_row(self):
        rows = sorted(set(index.row() for index in self.table.selectedIndexes()), reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def check_and_save(self):
        seen_ids = set()
        seen_names = set()
        row_count = self.table.rowCount()
        for row in range(row_count):
            item_id = self.table.item(row, 0)
            item_name = self.table.item(row, 1)
            pid = item_id.text().strip() if item_id else ""
            name = item_name.text().strip() if item_name else ""
            if not pid: continue
            if pid in seen_ids:
                QMessageBox.warning(self, "数据重复", f"第 {row+1} 行的商品条码 '{pid}' 与之前重复！")
                self.table.selectRow(row)
                return
            if name in seen_names:
                QMessageBox.warning(self, "数据重复", f"第 {row+1} 行的商品名称 '{name}' 与之前重复！")
                self.table.selectRow(row)
                return
            seen_ids.add(pid)
            seen_names.add(name)
        self.accept()

    def get_table_data(self):
        new_list = []
        for row in range(self.table.rowCount()):
            pid = self.table.item(row, 0).text().strip() if self.table.item(row, 0) else ""
            name = self.table.item(row, 1).text().strip() if self.table.item(row, 1) else ""
            price = self.table.item(row, 2).text().strip() if self.table.item(row, 2) else "0.00"
            if pid: new_list.append({'id': pid, 'name': name, 'price': price})
        return new_list

# ==========================================
# 5. 串口工作线程
# ==========================================
class SerialWorker(QThread):
    log_signal = Signal(str)
    packet_signal = Signal(dict)
    connection_success_signal = Signal(bool)

    def __init__(self):
        super().__init__()
        self.ser = None
        self.is_running = False
        self.port = ""
        self.baud = 115200

    def start_serial(self, port, baud):
        self.port = port
        self.baud = baud
        self.start()

    def run(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,                
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            self.ser.setDTR(False)
            self.ser.setRTS(False)
            self.ser.reset_input_buffer()

            self.is_running = True
            self.connection_success_signal.emit(True)
            self.log_signal.emit(f"成功连接到 {self.port}")
            
            while self.is_running:
                if self.ser and self.ser.in_waiting:
                    try:
                        line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            if line.startswith("CMD:"):
                                self.parse_line(line)
                            else:
                                self.log_signal.emit(f"[原始] {line}")
                    except Exception as e:
                        self.log_signal.emit(f"读取错误: {e}")
                self.msleep(10) 
        except Exception as e:
            self.log_signal.emit(f"串口打开失败: {e}")
            self.connection_success_signal.emit(False)
            self.is_running = False

    def stop(self):
        self.is_running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except:
                pass
        self.log_signal.emit("串口已关闭")

    def send(self, text):
        if self.ser and self.ser.is_open:
            try:
                data = (text + '\n').encode('utf-8')
                self.ser.write(data)
                self.log_signal.emit(f"[发送] {text}")
            except Exception as e:
                self.log_signal.emit(f"发送失败: {e}")
        else:
            self.log_signal.emit("错误: 串口未连接，无法发送")

    def parse_line(self, line):
        self.log_signal.emit(f"[接收] {line}")
        try:
            parts = line.split(',')
            data = {}
            for part in parts:
                if ':' in part:
                    k, v = part.split(':', 1)
                    data[k.strip()] = v.strip()
            if data:
                self.packet_signal.emit(data)
        except Exception as e:
            self.log_signal.emit(f"协议解析错误: {e}")

# ... (ProductManager, DailyReportDialog, ScanSimulationDialog, SerialWorker 保持原样) ...

# ==========================================
# 6. 主界面 (修改版 - 适配新协议)
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("无人超市上位机 V3.0 (SPI Flash同步版)")
        self.resize(1000, 600)
        
        self.pm = ProductManager()
        self.worker = SerialWorker()
        
        # [新增] 同步状态控制变量
        self.is_syncing = False          # 是否处于同步流程中
        self.sync_data_buffer = []       # 待发送的数据缓存
        
        self.worker.log_signal.connect(self.append_log)
        self.worker.packet_signal.connect(self.handle_packet)
        self.worker.connection_success_signal.connect(self.handle_connection_status)
        
        self.init_ui()

    def init_ui(self):
        # ... (界面布局代码保持不变，与你原代码一致) ...
        # 为了节省篇幅，这里省略重复的布局代码，直接复用你原有的 init_ui 即可
        # 只要确保 self.btn_scan_test 绑定了 self.open_scan_simulation
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # --- 左侧控制栏 ---
        left_panel = QVBoxLayout()
        
        # 1. 串口设置
        setting_box = QGroupBox("串口设置")
        setting_layout = QVBoxLayout()
        self.combo_ports = QComboBox()
        self.refresh_ports()
        setting_layout.addWidget(QLabel("端口:"))
        setting_layout.addWidget(self.combo_ports)
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["9600", "115200"])
        self.combo_baud.setCurrentText("115200")
        setting_layout.addWidget(QLabel("波特率:"))
        setting_layout.addWidget(self.combo_baud)
        self.btn_connect = QPushButton("打开串口")
        self.btn_connect.setCheckable(True) 
        self.btn_connect.clicked.connect(self.toggle_serial)
        setting_layout.addWidget(self.btn_connect)
        setting_box.setLayout(setting_layout)
        left_panel.addWidget(setting_box)

        # 2. 核心功能区
        func_box = QGroupBox("功能控制")
        func_layout = QVBoxLayout()
        
        self.btn_manage = QPushButton("📝 管理商品信息库")
        self.btn_manage.setStyleSheet("background-color: #FF9800; color: white;")
        self.btn_manage.clicked.connect(self.open_product_editor)
        func_layout.addWidget(self.btn_manage)
        
        self.btn_daily_report = QPushButton("📊 今日销售统计")
        self.btn_daily_report.setStyleSheet("background-color: #009688; color: white;")
        self.btn_daily_report.clicked.connect(self.open_daily_report)
        func_layout.addWidget(self.btn_daily_report)

        self.btn_clear_log = QPushButton("🧹 清空调试日志")
        self.btn_clear_log.setStyleSheet("background-color: #757575; color: white;") 
        self.btn_clear_log.clicked.connect(self.clear_logs)
        func_layout.addWidget(self.btn_clear_log)
        
        self.btn_scan_test = QPushButton("🔍 模拟扫码 (选择)")
        self.btn_scan_test.clicked.connect(self.open_scan_simulation) 
        func_layout.addWidget(self.btn_scan_test)
        
        func_box.setLayout(func_layout)
        left_panel.addWidget(func_box)
        
        left_panel.addStretch() 
        
        # --- 右侧显示栏 ---
        right_panel = QVBoxLayout()
        self.lbl_status = QLabel("串口未连接")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.update_status_style("disconnected") 
        right_panel.addWidget(self.lbl_status)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["时间", "条码", "商品名称", "单价", "数量"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_panel.addWidget(self.table)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        right_panel.addWidget(self.log_text)

        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 3)

    # ... (clear_logs, open_scan_simulation, open_product_editor, open_daily_report 保持不变) ...
    def clear_logs(self):
        self.log_text.clear()

    def open_scan_simulation(self):
        if not self.worker.is_running:
             QMessageBox.warning(self, "提示", "请先连接串口，否则无法发送指令。")
             return
        current_data = self.pm.get_all_list()
        dialog = ScanSimulationDialog(current_data, self)
        if dialog.exec() == QDialog.Accepted:
            target_id = dialog.selected_id
            if target_id:
                cmd = f"CMD:SCAN,ID:{target_id}"
                self.worker.send(cmd)

    def open_product_editor(self):
        current_data = self.pm.get_all_list()
        dialog = ProductEditorDialog(current_data, self)
        if dialog.exec() == QDialog.Accepted:
            new_data = dialog.get_table_data()
            if self.pm.save_data(new_data):
                self.append_log("系统: 商品库已保存")
                
                # 询问用户是否立即同步
                reply = QMessageBox.question(self, "同步", "数据已保存。是否立即同步到下位机 Flash？", 
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    self.start_sync_phase1() # 调用新的第一阶段
            else:
                QMessageBox.warning(self, "失败", "保存文件失败")

    def open_daily_report(self):
        dialog = DailyReportDialog(self)
        dialog.exec()

    # ==========================================
    # [重点修改] 同步逻辑 V2.0
    # 流程：发送Start -> 等待REQ_SYNC -> 逐条发送Data -> 发送End
    # ==========================================
    
    # 阶段一：发起同步请求
    def start_sync_phase1(self):
        if not self.worker.is_running:
            QMessageBox.warning(self, "警告", "串口未连接，无法同步！")
            return

        # 1. 准备数据
        self.sync_data_buffer = self.pm.get_all_list()
        total_count = len(self.sync_data_buffer)

        # 2. 发送启动指令 (包含总数) 
        # 格式: CMD:SYNC_START,TOTAL:数量
        cmd = f"CMD:SYNC_START,TOTAL:{total_count}"
        self.worker.send(cmd)

        # 3. 进入等待状态
        self.is_syncing = True
        self.lbl_status.setText(f"⏳ 等待下位机擦除Flash... (共 {total_count} 条)")
        self.update_status_style("warning") # 黄色警告色，表示忙碌
        
        # 此时不能立即发送数据，必须等待 handle_packet 收到 REQ_SYNC

    # 阶段二：接收握手信号并传输数据
    def start_sync_phase2_transmission(self):
        if not self.is_syncing: return

        self.lbl_status.setText("🚀 正在写入 Flash (请勿断电)...")
        total = len(self.sync_data_buffer)
        
        # 遍历发送数据 [cite: 43]
        for i, item in enumerate(self.sync_data_buffer):
            # 格式: CMD:SYNC_DATA,ID:xxx,PR:xxx,NM:xxx [cite: 21]
            cmd = f"CMD:SYNC_DATA,ID:{item['id']},PR:{item['price']},NM:{item['name']}"
            self.worker.send(cmd)
            
            # [关键] 流控保护：微小延时，防止串口缓冲区溢出或Flash写入来不及 
            # 这里使用了 processEvents 防止界面在循环中卡死
            time.sleep(0.02) # 20ms
            QApplication.processEvents() 
            
            # 更新状态栏显示进度
            if i % 5 == 0:
                self.lbl_status.setText(f"🚀 正在写入... ({i+1}/{total})")

        # 发送结束指令 
        # 格式: CMD:SYNC_END,SUM:数量
        self.worker.send(f"CMD:SYNC_END,SUM:{total}")
        
        self.is_syncing = False
        self.lbl_status.setText(f"✅ 同步完成！共写入 {total} 条数据")
        self.update_status_style("normal")
        self.append_log(f"同步流程结束，发送完毕。")
        QMessageBox.information(self, "完成", "数据已成功同步至下位机 Flash！")

    # ... (update_status_style, refresh_ports, toggle_serial, handle_connection_status, append_log 保持不变) ...
    def update_status_style(self, state):
        base_style = "font-size: 16px; padding: 10px; border-radius: 4px;"
        if state == "normal":
            self.lbl_status.setStyleSheet(f"background-color: #4CAF50; color: white; {base_style}")
        elif state == "disconnected":
            self.lbl_status.setText("串口未连接")
            self.lbl_status.setStyleSheet(f"background-color: #9E9E9E; color: white; {base_style}")
        elif state == "error":
            self.lbl_status.setStyleSheet(f"background-color: #F44336; color: white; font-weight: bold; {base_style}")
        elif state == "item":
            self.lbl_status.setStyleSheet(f"background-color: #2196F3; color: white; {base_style}")
        elif state == "warning": # 新增
            self.lbl_status.setStyleSheet(f"background-color: #FFC107; color: black; {base_style}")

    def refresh_ports(self):
        self.combo_ports.clear()
        ports = serial.tools.list_ports.comports()
        if not ports: self.combo_ports.addItem("无可用串口")
        else:
            for p in ports: self.combo_ports.addItem(f"{p.device}")

    def toggle_serial(self):
        if self.btn_connect.isChecked():
            port = self.combo_ports.currentText()
            if not port or "无" in port:
                self.btn_connect.setChecked(False)
                return
            baud = int(self.combo_baud.currentText())
            self.worker.start_serial(port, baud)
        else:
            self.worker.stop()
            self.btn_connect.setText("打开串口")
            self.update_status_style("disconnected")

    @Slot(bool)
    def handle_connection_status(self, success):
        if success:
            self.lbl_status.setText("系统就绪 - 监听中")
            self.update_status_style("normal")
            self.btn_connect.setText("关闭串口")
        else:
            self.lbl_status.setText("连接失败")
            self.update_status_style("error")
            self.btn_connect.setChecked(False)

    def append_log(self, text):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{t}] {text}")
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        
        if "[发送]" in text:
            content = text.replace("[发送]", "").strip()
            # 如果不是大量同步数据，才显示在状态栏，避免闪烁过快
            if "SYNC_DATA" not in content:
                self.lbl_status.setText(f"📤 发送: {content}")
        elif "[接收]" in text:
            content = text.replace("[接收]", "").strip()
            self.lbl_status.setText(f"📥 接收: {content}")

    # ==========================================
    # [重点修改] 协议解析逻辑
    # ==========================================
    def handle_packet(self, data):
        cmd = data.get('CMD')
        
        # 1. 销售上报
        if cmd == 'REPORT':
            barcode = data.get('ID')
            qty = data.get('QT', '1')
            name, price = self.pm.get_info(barcode)
            
            row = self.table.rowCount()
            self.table.insertRow(row)
            t_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.table.setItem(row, 0, QTableWidgetItem(t_str))
            self.table.setItem(row, 1, QTableWidgetItem(barcode))
            self.table.setItem(row, 2, QTableWidgetItem(name))
            self.table.setItem(row, 3, QTableWidgetItem(f"{price:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(qty))
            self.table.scrollToBottom()
            
            self.save_sale_record(t_str, barcode, name, price, qty)
            self.lbl_status.setText(f"✅ 结算成功: {name} x{qty}")
            self.update_status_style("item")

        # 2. 报警处理
        elif cmd == 'ALARM':
            msg = data.get('MSG', '未知错误')
            self.lbl_status.setText(f"🚨 紧急报警: {msg}")
            self.update_status_style("error")
            QMessageBox.critical(self, "紧急警报", msg)

        # 3. [修改] 请求同步 / 握手信号
        elif cmd == 'REQ_SYNC':
            # 情况A: 我们处于同步流程中 (is_syncing=True)，这是STM32擦除完毕的信号
            if self.is_syncing:
                self.append_log("握手成功：收到 REQ_SYNC，开始传输数据...")
                self.start_sync_phase2_transmission()
            
            # 情况B: 我们没在同步，下位机主动请求 (可能是刚上电发现数据坏了)
            else:
                reply = QMessageBox.question(self, "同步请求", "下位机请求更新商品库，是否开始同步？", 
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    self.start_sync_phase1()

    def save_sale_record(self, time, barcode, name, price, qty):
        try:
            with open('sales_record.csv', 'a', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                if not os.path.exists('sales_record.csv'):
                    writer.writerow(['Time', 'Barcode', 'Name', 'Price', 'Quantity'])
                writer.writerow([time, barcode, name, price, qty])
        except Exception as e:
            self.append_log(f"保存CSV失败: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())