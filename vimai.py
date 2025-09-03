import os
import re
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QTreeView, QTextEdit, QLineEdit, QLabel, QSplitter, 
                            QStatusBar, QMenu, QInputDialog, QMessageBox, QFileDialog,
                            QPlainTextEdit, QPushButton, QFileIconProvider, QStyle, QToolTip)
from PyQt5.QtCore import Qt, QDir, QModelIndex, QAbstractItemModel, QTimer, QProcess, QSize, QRect, QPoint
from PyQt5.QtGui import (QFont, QTextCursor, QSyntaxHighlighter, QTextCharFormat, 
                         QColor, QKeySequence, QTextDocument, QKeyEvent, QIcon, QTextBlockFormat,
                         QPainter, QTextFormat, QPalette, QTextOption, QBrush, QPen)
# Gemini AI imports with error handling
try:
    import google.generativeai as genai
    from google.api_core.exceptions import InvalidArgument
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Neovim-inspired color palette
COLORS = {
    'bg': '#1e1e2e',
    'fg': '#cdd6f4',
    'comment': '#6c7086',
    'selection': '#45475a',
    'cursor': '#f5e0dc',
    'statusline': '#181825',
    'linenr': '#6c7086',
    'linenr_fg': '#6c7086',
    'error': '#f38ba8',
    'warning': '#fab387',
    'info': '#89b4fa',
    'hint': '#a6e3a1',
    'menu': '#313244',
    'menu_sel': '#585b70',
    'special': '#f5c2e7',
    'vertsplit': '#313244',
    'sign_column': '#1e1e2e',
    'fold_column': '#313244',
    'yellow': '#f9e2af',
    'purple': '#cba6f7',
    'blue': '#89b4fa',
}

class CustomIconProvider(QFileIconProvider):
    def __init__(self):
        super().__init__()
        self.style = QApplication.style()
        
    def icon(self, type_or_info):
        if isinstance(type_or_info, str):
            # Handle by file type string
            file_type = type_or_info
            if file_type == 'dir':
                icon = QIcon.fromTheme('folder')
                if icon.isNull():
                    icon = self.style.standardIcon(QStyle.SP_DirIcon)
                return icon
            else:
                # Handle by file extension
                if file_type.endswith('.py'):
                    icon = QIcon.fromTheme('text-x-python')
                    if icon.isNull():
                        icon = self.style.standardIcon(QStyle.SP_FileIcon)
                elif file_type.endswith('.js'):
                    icon = QIcon.fromTheme('text-x-javascript')
                    if icon.isNull():
                        icon = self.style.standardIcon(QStyle.SP_FileIcon)
                elif file_type.endswith('.md'):
                    icon = QIcon.fromTheme('text-x-markdown')
                    if icon.isNull():
                        icon = self.style.standardIcon(QStyle.SP_FileIcon)
                elif file_type.endswith(('.c', '.cpp', '.h')):
                    icon = QIcon.fromTheme('text-x-c++src')
                    if icon.isNull():
                        icon = self.style.standardIcon(QStyle.SP_FileIcon)
                elif file_type.endswith('.java'):
                    icon = QIcon.fromTheme('text-x-java')
                    if icon.isNull():
                        icon = self.style.standardIcon(QStyle.SP_FileIcon)
                else:
                    icon = QIcon.fromTheme('text-x-generic')
                    if icon.isNull():
                        icon = self.style.standardIcon(QStyle.SP_FileIcon)
                return icon
        else:
            # Default behavior
            return super().icon(type_or_info)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.error_lines = set()
        self.warning_lines = set()
        self.info_lines = set()
        self.error_messages = {}
        self.warning_messages = {}
        self.info_messages = {}
        self.setMouseTracking(True)
        
    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(COLORS['sign_column']))
        
        block = self.editor.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
        bottom = top + self.editor.blockBoundingRect(block).height()
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible():
                number = str(block_number + 1)
                painter.setPen(QColor(COLORS['linenr_fg']))
                
                # Draw line number
                painter.drawText(0, int(top), self.width() - 15, self.editor.fontMetrics().height(),
                                Qt.AlignRight, number)
                
                # Draw error/warning/info indicators
                line_number = block_number + 1
                x_pos = self.width() - 12
                
                if line_number in self.error_lines:
                    painter.setPen(QColor(COLORS['error']))
                    painter.drawText(x_pos, int(top), 10, self.editor.fontMetrics().height(),
                                    Qt.AlignLeft, "✗")
                elif line_number in self.warning_lines:
                    painter.setPen(QColor(COLORS['warning']))
                    painter.drawText(x_pos, int(top), 10, self.editor.fontMetrics().height(),
                                    Qt.AlignLeft, "⚠")
                elif line_number in self.info_lines:
                    painter.setPen(QColor(COLORS['info']))
                    painter.drawText(x_pos, int(top), 10, self.editor.fontMetrics().height(),
                                    Qt.AlignLeft, "ℹ")
                
            block = block.next()
            top = bottom
            bottom = top + self.editor.blockBoundingRect(block).height()
            block_number += 1
            
    def set_errors(self, lines, messages=None):
        self.error_lines = set(lines)
        if messages:
            self.error_messages = messages
        self.update()
        
    def set_warnings(self, lines, messages=None):
        self.warning_lines = set(lines)
        if messages:
            self.warning_messages = messages
        self.update()
        
    def set_info(self, lines, messages=None):
        self.info_lines = set(lines)
        if messages:
            self.info_messages = messages
        self.update()
        
    def mouseMoveEvent(self, event):
        # Calculate the line number under the mouse
        block = self.editor.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
        bottom = top + self.editor.blockBoundingRect(block).height()
        
        while block.isValid() and top <= event.y():
            if block.isVisible():
                # Check if the mouse is over the indicator area
                x_pos = self.width() - 12
                if event.x() >= x_pos and event.x() <= x_pos + 10:
                    line_number = block_number + 1
                    tooltip = ""
                    if line_number in self.error_messages:
                        tooltip = f"Error: {self.error_messages[line_number]}"
                    elif line_number in self.warning_messages:
                        tooltip = f"Warning: {self.warning_messages[line_number]}"
                    elif line_number in self.info_messages:
                        tooltip = f"Info: {self.info_messages[line_number]}"
                    
                    if tooltip:
                        QToolTip.showText(event.globalPos(), tooltip)
                        return
            
            block = block.next()
            top = bottom
            bottom = top + self.editor.blockBoundingRect(block).height()
            block_number += 1
        
        QToolTip.hideText()

class VimTextEdit(QPlainTextEdit):
    def __init__(self, parent_editor):
        super().__init__()
        self.parent_editor = parent_editor
        self.line_number_area = None
        
    def line_number_area_width(self):
        digits = 1
        max_value = max(1, self.blockCount())
        while max_value >= 10:
            max_value /= 10
            digits += 1
        space = 15 + self.fontMetrics().width('9') * digits
        return space
        
    def update_line_number_area_width(self):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
        
    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
            
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.line_number_area:
            cr = self.contentsRect()
            self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))
        
    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            QPlainTextEdit.keyPressEvent(self, event)
            return
            
        if self.parent_editor.insert_mode:
            if event.key() == Qt.Key_Escape:
                self.parent_editor.set_normal_mode()
            else:
                QPlainTextEdit.keyPressEvent(self, event)
        else:
            self.parent_editor.vim_key_handler(event)

class VirtualFileSystemModel(QAbstractItemModel):
    """A virtual file system that doesn't touch the real filesystem"""
    def __init__(self):
        super().__init__()
        self.icon_provider = CustomIconProvider()
        self.root = {
            'name': 'workspace',
            'type': 'dir',
            'children': [
                {
                    'name': 'src',
                    'type': 'dir',
                    'children': [
                        {'name': 'main.py', 'type': 'file', 'content': '# Python starter code\nprint("Hello VimAI!")'},
                        {'name': 'utils.py', 'type': 'file', 'content': '# Utility functions\ndef greet(name):\n    return f"Hello {name}"'},
                        {'name': 'testing.c', 'type': 'file', 'content': '#include <stdio.h>\n\nint main() {\n    printf("Hello, C World!\\n");\n    return 0;\n}'},
                        {'name': 'testing.cpp', 'type': 'file', 'content': '#include <iostream>\n\nint main() {\n    std::cout << "Hello, C++ World!" << std::endl;\n    return 0;\n}'}
                    ]
                },
                {
                    'name': 'docs',
                    'type': 'dir',
                    'children': [
                        {'name': 'README.md', 'type': 'file', 'content': '# Project Documentation\n\nThis is a VimAI project.'}
                    ]
                }
            ]
        }
        
    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
            
        if not parent.isValid():
            parent_item = self.root
        else:
            parent_item = parent.internalPointer()
            
        child_item = parent_item['children'][row]
        return self.createIndex(row, column, child_item)
        
    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
            
        child_item = index.internalPointer()
        parent_item = self.find_parent(self.root, child_item)
        
        if parent_item == self.root:
            return QModelIndex()
            
        grandparent = self.find_parent(self.root, parent_item)
        row = grandparent['children'].index(parent_item)
        return self.createIndex(row, 0, parent_item)
        
    def find_parent(self, current, target):
        if 'children' in current:
            for child in current['children']:
                if child == target:
                    return current
                found = self.find_parent(child, target)
                if found:
                    return found
        return None
        
    def rowCount(self, parent=QModelIndex()):
        if parent.column() > 0:
            return 0
            
        if not parent.isValid():
            parent_item = self.root
        else:
            parent_item = parent.internalPointer()
            
        return len(parent_item['children']) if 'children' in parent_item else 0
        
    def columnCount(self, parent=QModelIndex()):
        return 1
        
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
            
        item = index.internalPointer()
        
        if role == Qt.DisplayRole:
            return item['name']
        elif role == Qt.DecorationRole:
            if item['type'] == 'dir':
                return self.icon_provider.icon('dir')
            else:
                return self.icon_provider.icon(item['name'])
                
    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        
    def add_file(self, parent_index, name, content=''):
        parent_item = parent_index.internalPointer() if parent_index.isValid() else self.root
        
        self.beginInsertRows(parent_index, len(parent_item['children']), len(parent_item['children']))
        parent_item['children'].append({
            'name': name,
            'type': 'file',
            'content': content
        })
        self.endInsertRows()
        
    def add_directory(self, parent_index, name):
        parent_item = parent_index.internalPointer() if parent_index.isValid() else self.root
        
        self.beginInsertRows(parent_index, len(parent_item['children']), len(parent_item['children']))
        parent_item['children'].append({
            'name': name,
            'type': 'dir',
            'children': []
        })
        self.endInsertRows()
        
    def remove_item(self, index):
        parent = index.parent()
        parent_item = parent.internalPointer() if parent.isValid() else self.root
        
        self.beginRemoveRows(parent, index.row(), index.row())
        del parent_item['children'][index.row()]
        self.endRemoveRows()
        
    def rename_item(self, index, new_name):
        item = index.internalPointer()
        item['name'] = new_name
        self.dataChanged.emit(index, index)

class VimAIEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VimAI Editor")
        self.resize(1200, 800)
        
        # Editor state
        self.vim_mode = True
        self.command_mode = False
        self.insert_mode = False
        self.last_action = None
        self.current_file = None
        self.modified = False
        self.cursor_history = []
        self.suggestion_pos = None
        
        # Initialize AI
        self.init_ai()
        
        # Terminal process
        self.terminal_process = QProcess()
        self.terminal_process.readyReadStandardOutput.connect(self.handle_terminal_output)
        self.terminal_process.readyReadStandardError.connect(self.handle_terminal_error)
        
        # Setup UI with Neovim-like interface
        self.init_ui()
        self.set_nvim_theme()
        
        # Command buffer
        self.command_buffer = ""
        self.command_timer = QTimer(self)
        self.command_timer.setSingleShot(True)
        self.command_timer.timeout.connect(self.reset_command_buffer)
        
        # Autocomplete
        self.completion_timer = QTimer(self)
        self.completion_timer.setSingleShot(True)
        self.completion_timer.timeout.connect(self.fetch_autocomplete)
        self.pending_completions = []
        
        # Auto-save timer
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(30000)  # Auto-save every 30 seconds
        
        # Auto-lint timer
        self.auto_lint_timer = QTimer(self)
        self.auto_lint_timer.setSingleShot(True)
        self.auto_lint_timer.timeout.connect(self.lint_code)
        
    def init_ui(self):
        """Initialize all UI components with Neovim-like interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Main splitter (file tree | editor panels)
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(1)
        main_layout.addWidget(main_splitter)
        
        # File tree panel (20% width)
        self.init_file_tree()
        main_splitter.addWidget(self.file_tree)
        
        # Right side splitter (editor | bottom panels)
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setHandleWidth(1)
        main_splitter.addWidget(right_splitter)
        
        # Editor panel (70% height)
        self.init_editor()
        right_splitter.addWidget(self.editor_container)
        
        # Bottom panels (30% height)
        bottom_splitter = QSplitter(Qt.Horizontal)
        bottom_splitter.setHandleWidth(1)
        right_splitter.addWidget(bottom_splitter)
        
        # AI panel (50% width)
        self.init_ai_panel()
        bottom_splitter.addWidget(self.ai_output_container)
        
        # Terminal panel (50% width)
        self.init_terminal()
        bottom_splitter.addWidget(self.terminal_container)
        
        # Status bar
        self.init_status_bar()
        
        # Set initial sizes
        main_splitter.setSizes([240, 960])
        right_splitter.setSizes([560, 240])
        bottom_splitter.setSizes([480, 480])
        
    def init_file_tree(self):
        """Initialize the file tree with Neovim style"""
        self.file_tree = QTreeView()
        self.file_tree.setHeaderHidden(True)
        self.file_model = VirtualFileSystemModel()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setIndentation(15)
        self.file_tree.setAnimated(False)
        
        # Neovim-like styling
        self.file_tree.setStyleSheet(f"""
            QTreeView {{
                background-color: {COLORS['bg']};
                color: {COLORS['fg']};
                border: none;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                padding: 5px;
                outline: 0;
            }}
            QTreeView::item {{
                height: 22px;
                padding: 2px;
            }}
            QTreeView::item:selected {{
                background-color: {COLORS['selection']};
                color: {COLORS['fg']};
            }}
            QTreeView::branch:has-siblings:!adjoins-item {{
                border-image: none;
            }}
            QTreeView::branch:has-siblings:adjoins-item {{
                border-image: none;
            }}
            QTreeView::branch:!has-children:!has-siblings:adjoins-item {{
                border-image: none;
            }}
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {{
                border-image: none;
                image: url(:/qss_icons/rc/branch_closed.png);
            }}
            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings  {{
                border-image: none;
                image: url(:/qss_icons/rc/branch_open.png);
            }}
        """)
        
        # Context menu
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.show_file_context_menu)
        self.file_tree.doubleClicked.connect(self.open_file)
        
    def init_editor(self):
        """Initialize the code editor with Neovim style"""
        self.editor_container = QWidget()
        editor_layout = QHBoxLayout(self.editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)
        
        # Main editor
        self.editor = VimTextEdit(self)
        self.editor.setFont(QFont("JetBrains Mono", 13))
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        
        # Create line number area
        self.editor.line_number_area = LineNumberArea(self.editor)
        
        # Connect signals
        self.editor.blockCountChanged.connect(self.editor.update_line_number_area_width)
        self.editor.updateRequest.connect(self.editor.update_line_number_area)
        self.editor.update_line_number_area_width()
        
        # Editor styling
        self.editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLORS['bg']};
                color: {COLORS['fg']};
                border: none;
                font-family: 'JetBrains Mono', monospace;
                font-size: 13px;
                padding: 5px;
                selection-background-color: {COLORS['selection']};
                selection-color: {COLORS['fg']};
            }}
        """)
        
        # Connect signals
        self.editor.textChanged.connect(self.set_modified)
        self.editor.textChanged.connect(self.trigger_auto_lint)
        
        # Syntax highlighter
        self.highlighter = CodeHighlighter(self.editor.document())
        
        editor_layout.addWidget(self.editor)
        
    def init_ai_panel(self):
        """Initialize the AI panel with Neovim style"""
        self.ai_output_container = QWidget()
        ai_layout = QVBoxLayout(self.ai_output_container)
        ai_layout.setContentsMargins(0, 0, 0, 0)
        ai_layout.setSpacing(0)
        
        # Panel label
        self.ai_label = QLabel("AI Assistant")
        self.ai_label.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS['statusline']};
                color: {COLORS['fg']};
                padding: 5px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
                border-bottom: 1px solid {COLORS['vertsplit']};
            }}
        """)
        ai_layout.addWidget(self.ai_label)
        
        # AI output area
        self.ai_output = QTextEdit()
        self.ai_output.setReadOnly(True)
        self.ai_output.setFont(QFont("JetBrains Mono", 11))
        self.ai_output.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg']};
                color: {COLORS['special']};
                border: none;
                padding: 5px;
                font-family: 'JetBrains Mono', monospace;
            }}
        """)
        ai_layout.addWidget(self.ai_output)
        
    def init_terminal(self):
        """Initialize the terminal panel with Neovim style"""
        self.terminal_container = QWidget()
        terminal_layout = QVBoxLayout(self.terminal_container)
        terminal_layout.setContentsMargins(0, 0, 0, 0)
        terminal_layout.setSpacing(0)
        
        # Panel header
        terminal_header = QWidget()
        terminal_header_layout = QHBoxLayout(terminal_header)
        terminal_header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.terminal_label = QLabel("Terminal")
        self.terminal_label.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS['statusline']};
                color: {COLORS['fg']};
                padding: 5px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
                border-bottom: 1px solid {COLORS['vertsplit']};
            }}
        """)
        
        self.run_button = QPushButton("Run")
        self.run_button.setFixedWidth(50)
        self.run_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['menu_sel']};
                color: {COLORS['fg']};
                border: none;
                padding: 3px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['selection']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['menu']};
            }}
        """)
        self.run_button.clicked.connect(self.run_current_file)
        
        terminal_header_layout.addWidget(self.terminal_label)
        terminal_header_layout.addWidget(self.run_button)
        terminal_layout.addWidget(terminal_header)
        
        # Terminal output
        self.terminal_output = QPlainTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setFont(QFont("JetBrains Mono", 11))
        self.terminal_output.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLORS['bg']};
                color: {COLORS['info']};
                border: none;
                padding: 5px;
                font-family: 'JetBrains Mono', monospace;
            }}
        """)
        terminal_layout.addWidget(self.terminal_output)
        
        # Terminal input
        self.terminal_input = QLineEdit()
        self.terminal_input.setPlaceholderText("Enter command...")
        self.terminal_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['statusline']};
                color: {COLORS['fg']};
                border: none;
                border-top: 1px solid {COLORS['vertsplit']};
                padding: 5px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
            }}
        """)
        self.terminal_input.returnPressed.connect(self.execute_terminal_command)
        terminal_layout.addWidget(self.terminal_input)
        
    def init_status_bar(self):
        """Initialize the status bar with Neovim style"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {COLORS['statusline']};
                color: {COLORS['fg']};
                border-top: 1px solid {COLORS['vertsplit']};
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
            }}
        """)
        
        # Mode indicator
        self.mode_label = QLabel("NORMAL")
        self.mode_label.setAlignment(Qt.AlignCenter)
        self.mode_label.setFixedWidth(80)
        self.mode_label.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS['menu_sel']};
                color: {COLORS['fg']};
                padding: 2px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
                font-weight: bold;
                border-radius: 3px;
            }}
        """)
        
        # File status
        self.file_status_label = QLabel()
        self.file_status_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['fg']};
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
            }}
        """)
        
        # AI status
        self.ai_status_label = QLabel()
        self.ai_status_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['fg']};
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
            }}
        """)
        
        # Add widgets to status bar
        self.status_bar.addPermanentWidget(self.mode_label)
        self.status_bar.addWidget(self.file_status_label)
        self.status_bar.addPermanentWidget(self.ai_status_label)
        
        self.update_status()
        
    def set_nvim_theme(self):
        """Apply a Neovim-like theme to the editor"""
        palette = self.palette()
        palette.setColor(palette.Window, QColor(COLORS['bg']))
        palette.setColor(palette.WindowText, QColor(COLORS['fg']))
        palette.setColor(palette.Base, QColor(COLORS['bg']))
        palette.setColor(palette.AlternateBase, QColor(COLORS['statusline']))
        palette.setColor(palette.ToolTipBase, QColor(COLORS['menu']))
        palette.setColor(palette.ToolTipText, QColor(COLORS['fg']))
        palette.setColor(palette.Text, QColor(COLORS['fg']))
        palette.setColor(palette.Button, QColor(COLORS['menu']))
        palette.setColor(palette.ButtonText, QColor(COLORS['fg']))
        palette.setColor(palette.BrightText, QColor(COLORS['error']))
        palette.setColor(palette.Highlight, QColor(COLORS['selection']))
        palette.setColor(palette.HighlightedText, QColor(COLORS['fg']))
        
        self.setPalette(palette)
        
        # Custom styling for the application
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['bg']};
            }}
            QSplitter::handle {{
                background-color: {COLORS['vertsplit']};
                width: 1px;
                height: 1px;
            }}
            QMenu {{
                background-color: {COLORS['menu']};
                color: {COLORS['fg']};
                border: 1px solid {COLORS['vertsplit']};
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['menu_sel']};
            }}
            QScrollBar:vertical {{
                border: none;
                background: {COLORS['bg']};
                width: 8px;
                margin: 0px 0px 0px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['menu']};
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::add-line:vertical {{
                border: none;
                background: none;
                height: 0px;
                subcontrol-position: bottom;
                subcontrol-origin: margin;
            }}
            QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
                height: 0px;
                subcontrol-position: top;
                subcontrol-origin: margin;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: {COLORS['bg']};
                height: 8px;
                margin: 0px 0px 0px 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {COLORS['menu']};
                min-width: 20px;
                border-radius: 4px;
            }}
        """)
        
    # File Management Functions
    def show_file_context_menu(self, position):
        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['menu']};
                color: {COLORS['fg']};
                border: 1px solid {COLORS['vertsplit']};
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['menu_sel']};
            }}
        """)
        index = self.file_tree.indexAt(position)
        
        if not index.isValid():
            menu.addAction("New File", lambda: self.create_new_file(index))
            menu.addAction("New Folder", lambda: self.create_new_folder(index))
        else:
            item = index.internalPointer()
            if item['type'] == 'dir':
                menu.addAction("New File", lambda: self.create_new_file(index))
                menu.addAction("New Folder", lambda: self.create_new_folder(index))
                menu.addSeparator()
            menu.addAction("Rename", lambda: self.rename_file(index))
            menu.addAction("Delete", lambda: self.delete_file(index))
        
        menu.exec_(self.file_tree.viewport().mapToGlobal(position))
        
    def create_new_file(self, parent_index):
        name, ok = QInputDialog.getText(self, "New File", "File name:")
        if ok and name:
            self.file_model.add_file(parent_index, name)
            
    def create_new_folder(self, parent_index):
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            self.file_model.add_directory(parent_index, name)
            
    def rename_file(self, index):
        old_name = index.internalPointer()['name']
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=old_name)
        if ok and new_name and new_name != old_name:
            self.file_model.rename_item(index, new_name)
            if self.current_file == old_name:
                self.current_file = new_name
                self.update_status()
                
    def delete_file(self, index):
        item = index.internalPointer()
        reply = QMessageBox.question(
            self, "Delete", 
            f"Are you sure you want to delete '{item['name']}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.current_file == item['name']:
                self.current_file = None
                self.editor.clear()
                self.update_status()
            self.file_model.remove_item(index)
            
    def open_file(self, index):
        item = index.internalPointer()
        if item['type'] == 'file':
            self.editor.setPlainText(item['content'])
            self.current_file = item['name']
            self.modified = False
            self.update_status()
            self.highlighter.set_document_language(item['name'])
            # Clear any existing error indicators
            self.editor.line_number_area.set_errors([])
            self.editor.line_number_area.set_warnings([])
            self.editor.line_number_area.set_info([])
            
    def save_file(self):
        if not self.current_file:
            return
            
        for item in self.file_model.root['children']:
            if self.update_file_content(item, self.current_file, self.editor.toPlainText()):
                self.modified = False
                self.update_status()
                self.ai_output.setPlainText(f"Saved {self.current_file}")
                return
                
        self.ai_output.setPlainText(f"Could not save {self.current_file}")
        
    def update_file_content(self, item, filename, content):
        if item['type'] == 'file' and item['name'] == filename:
            item['content'] = content
            return True
            
        if 'children' in item:
            for child in item['children']:
                if self.update_file_content(child, filename, content):
                    return True
        return False
        
    # Editor Core Functions
    def update_status(self):
        if self.current_file:
            file_status = f"{self.current_file}"
            if self.modified:
                file_status += " [modified]"
        else:
            file_status = "No file open"
            
        self.file_status_label.setText(file_status)
        
        ai_status = "AI: " + ("✓" if self.ai_connected else "✗")
        self.ai_status_label.setText(ai_status)
        
    def set_modified(self):
        if not self.modified and self.current_file:
            self.modified = True
            self.update_status()
            
    # Auto-save functionality
    def auto_save(self):
        if self.modified and self.current_file:
            self.save_file()
            self.ai_output.appendPlainText("Auto-saved file")
            
    # Auto-lint functionality
    def trigger_auto_lint(self):
        self.auto_lint_timer.start(1000)  # Trigger linting after 1 second of inactivity
        
    # Vim Emulation Functions
    def keyPressEvent(self, event):
        if self.command_mode or self.insert_mode:
            QMainWindow.keyPressEvent(self, event)
            return
            
        key = event.key()
        text = event.text()
        
        if text == ':':
            self.set_command_mode()
        elif text == 'i':
            self.set_insert_mode()
            self.editor.setFocus()
        elif text == 'a':
            self.editor.moveCursor(QTextCursor.Right)
            self.set_insert_mode()
            self.editor.setFocus()
        else:
            QMainWindow.keyPressEvent(self, event)
            
    def vim_key_handler(self, event):
        key = event.key()
        text = event.text()
        modifiers = event.modifiers()
    
        if self.command_mode:
            if key == Qt.Key_Escape:
                self.set_normal_mode()
            elif key == Qt.Key_Return:
                self.execute_vim_command(self.command_buffer)
                self.command_buffer = ""
                self.set_normal_mode()
            elif key == Qt.Key_Backspace:
                self.command_buffer = self.command_buffer[:-1]
            elif text:
                self.command_buffer += text
            
            self.update_command_status()
            return
        
        if self.vim_mode and not modifiers:
            if text == ':':
                self.set_command_mode()
                return
            elif text == 'i':
                self.set_insert_mode()
                return
            elif text == 'a':
                self.editor.moveCursor(QTextCursor.Right)
                self.set_insert_mode()
                return
            elif text == 'h':
                self.editor.moveCursor(QTextCursor.Left)
            elif text == 'j':
                self.editor.moveCursor(QTextCursor.Down)
            elif text == 'k':
                self.editor.moveCursor(QTextCursor.Up)
            elif text == 'l':
                self.editor.moveCursor(QTextCursor.Right)
            elif text == 'x':
                self.editor.textCursor().deleteChar()
            elif text == 'd' and self.last_action == 'd':
                cursor = self.editor.textCursor()
                cursor.select(QTextCursor.LineUnderCursor)
                cursor.removeSelectedText()
            elif text == 'u' and self.last_action not in ['u', 'ctrl+r']:
                self.editor.undo()
            elif modifiers == Qt.ControlModifier and text == 'r':
                self.editor.redo()
            elif text == 'G':
                self.editor.moveCursor(QTextCursor.End)
            elif text == 'gg':
                self.editor.moveCursor(QTextCursor.Start)
            
            self.last_action = text
            return
        
        QPlainTextEdit.keyPressEvent(self.editor, event)
            
    def set_normal_mode(self):
        self.vim_mode = True
        self.command_mode = False
        self.insert_mode = False
        self.mode_label.setText("NORMAL")
        self.mode_label.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS['menu_sel']};
                color: {COLORS['fg']};
                padding: 2px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
                font-weight: bold;
                border-radius: 3px;
            }}
        """)
        
    def set_insert_mode(self):
        self.vim_mode = True
        self.command_mode = False
        self.insert_mode = True
        self.mode_label.setText("INSERT")
        self.mode_label.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS['hint']};
                color: {COLORS['bg']};
                padding: 2px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
                font-weight: bold;
                border-radius: 3px;
            }}
        """)
        self.editor.setFocus()
        
    def set_command_mode(self):
        self.vim_mode = True
        self.command_mode = True
        self.insert_mode = False
        self.command_buffer = ":"
        self.mode_label.setText("COMMAND")
        self.mode_label.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS['error']};
                color: {COLORS['bg']};
                padding: 2px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
                font-weight: bold;
                border-radius: 3px;
            }}
        """)
        self.update_command_status()
        
    def update_command_status(self):
        self.file_status_label.setText(self.command_buffer)
        
    def reset_command_buffer(self):
        if self.command_buffer and not self.command_mode:
            self.command_buffer = ""
            self.update_status()
            
    def execute_vim_command(self, command):
        if command.startswith(":w"):
            self.save_file()
        elif command.startswith(":wq"):
            self.save_file()
            self.close()
        elif command.startswith(":q"):
            self.close()
        elif command.startswith(":e "):
            file_name = command[3:].strip()
            self.find_and_open_file(file_name)
        elif command.startswith(":ai "):
            self.call_ai(command[4:], self.editor.toPlainText())
        elif command == ":fix":
            self.call_ai("Find and fix any bugs in this code:", self.editor.toPlainText())
        elif command == ":explain":
            self.explain_code()
        elif command == ":opt":
            self.call_ai("Optimize this code for better performance or readability:", self.editor.toPlainText())
        elif command == ":test":
            self.call_ai("Generate unit tests for this code:", self.editor.toPlainText())
        elif command == ":run":
            self.run_current_file()
        elif command.startswith(":lint"):
            self.lint_code()
        else:
            self.ai_output.setPlainText(f"Unknown command: {command}")
            
    def lint_code(self):
        """Simulate code linting and show errors in the line number area"""
        if not self.current_file:
            self.ai_output.setPlainText("No file open to lint")
            return
            
        # Simulate linting errors
        content = self.editor.toPlainText()
        lines = content.split('\n')
        error_lines = []
        warning_lines = []
        info_lines = []
        error_messages = {}
        warning_messages = {}
        info_messages = {}
        
        # Simple linting simulation
        for i, line in enumerate(lines, 1):
            # Check for potential issues
            if 'import' in line and 'from' not in line and 'import os' not in line:
                warning_lines.append(i)
                warning_messages[i] = "Consider using 'from module import name' instead of 'import module'"
            if 'print(' in line and 'f"' not in line and "'" not in line:
                info_lines.append(i)
                info_messages[i] = "Consider using f-strings for better readability"
            if 'TODO' in line or 'FIXME' in line:
                error_lines.append(i)
                error_messages[i] = "TODO or FIXME found"
            if '    ' in line and not line.strip().startswith('#'):
                # Potential indentation issue
                if i > 1 and not lines[i-2].strip().endswith(':'):
                    warning_lines.append(i)
                    warning_messages[i] = "Potential indentation issue"
        
        # Update line number area with errors
        self.editor.line_number_area.set_errors(error_lines, error_messages)
        self.editor.line_number_area.set_warnings(warning_lines, warning_messages)
        self.editor.line_number_area.set_info(info_lines, info_messages)
        
        # Show summary in AI panel
        error_count = len(error_lines)
        warning_count = len(warning_lines)
        info_count = len(info_lines)
        
        summary = f"Linting complete:\n"
        summary += f"Errors: {error_count}\n"
        summary += f"Warnings: {warning_count}\n"
        summary += f"Info: {info_count}\n\n"
        
        if error_lines:
            summary += f"Errors on lines: {', '.join(map(str, error_lines))}\n"
        if warning_lines:
            summary += f"Warnings on lines: {', '.join(map(str, warning_lines))}\n"
        if info_lines:
            summary += f"Info on lines: {', '.join(map(str, info_lines))}\n"
            
        self.ai_output.setPlainText(summary)
        
    def find_and_open_file(self, filename):
        for item in self.file_model.root['children']:
            if self.search_and_open(item, filename):
                return
        self.ai_output.setPlainText(f"File not found: {filename}")
        
    def search_and_open(self, item, filename):
        if item['type'] == 'file' and item['name'] == filename:
            self.editor.setPlainText(item['content'])
            self.current_file = item['name']
            self.modified = False
            self.update_status()
            self.highlighter.set_document_language(item['name'])
            return True
            
        if 'children' in item:
            for child in item['children']:
                if self.search_and_open(child, filename):
                    return True
        return False
        
    # AI Integration Functions
    def init_ai(self):
        """Initialize the Gemini AI connection"""
        self.ai_ready = False
        self.ai_connected = False
        if GEMINI_AVAILABLE:
            try:
                genai.configure(api_key="AIzaSyAxUpxqd2ZlLUIAJ41mNUoElET-cgQKeyE")  
                self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
                self.ai_ready = True
                self.ai_connected = True
                print("Gemini AI initialized successfully")
            except Exception as e:
                print(f"Gemini initialization error: {e}")
        else:
            print("Google GenerativeAI package not available")
    
    def call_ai(self, prompt: str, context: str):
        """Call the AI with the given prompt and context"""
        if not self.ai_ready:
            self.ai_output.setPlainText("❌ Gemini AI not available\nPlease install: pip install google-generativeai")
            return
        
        self.ai_output.setPlainText("🔄 Asking Gemini...")
        QApplication.processEvents()  # Force UI update
        
        try:
            full_prompt = f"{prompt}\n\n```\n{context}\n```"
            
            response = self.gemini_model.generate_content(
                full_prompt,
                generation_config={
                    "max_output_tokens": 2000,
                    "temperature": 0.5,
                }
            )
            
            if response.text:
                self.ai_output.setPlainText(response.text)
            else:
                self.ai_output.setPlainText("❌ No response text received from Gemini")
                
        except Exception as e:
            self.ai_output.setPlainText(f"❌ Gemini Error: {str(e)}")
            
    def explain_code(self):
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            self.call_ai("Explain this code:", selected_text)
        else:
            cursor.select(QTextCursor.LineUnderCursor)
            selected_text = cursor.selectedText()
            self.call_ai("Explain this line of code:", selected_text)
            
    def fetch_autocomplete(self):
        """Get autocomplete suggestions from AI"""
        if not self.ai_connected or not self.current_file:
            return
        
        cursor = self.editor.textCursor()
        cursor.select(QTextCursor.LineUnderCursor)
        line_text = cursor.selectedText()
        pos = cursor.positionInBlock()
    
        # Get context around cursor
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        line = cursor.selectedText()
    
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, pos)
        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        context_before = cursor.selectedText()
    
        # Only fetch completions for meaningful contexts
        if len(context_before.strip()) < 3:
            return
        
        try:
            response = self.gemini_model.generate_content(
                f"Suggest code completions for: {context_before}",
                generation_config={
                    "max_output_tokens": 100,
                    "temperature": 0.2,
                }
            )
        
            if response.text:
                suggestions = [line.strip() for line in response.text.split('\n') if line.strip()]
                if suggestions:
                    self.show_completions(suggestions, cursor.position())
                
        except Exception as e:
            print(f"Autocomplete error: {str(e)}")
            
    def show_completions(self, suggestions, pos):
        """Display autocomplete suggestions"""
        # Store the position where suggestions should be inserted
        self.suggestion_pos = pos
    
        # Create a popup or show in AI panel
        self.ai_output.setPlainText("Suggestions:\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(suggestions[:3])))
        
    # Terminal Functions
    def execute_terminal_command(self):
        command = self.terminal_input.text()
        if not command:
            return
            
        self.terminal_output.appendPlainText(f"$ {command}")
        self.terminal_input.clear()
        
        if command == "clear":
            self.terminal_output.clear()
            return
            
        if command.startswith("python ") and self.current_file and self.current_file.endswith('.py'):
            self.run_current_file()
            return
            
        self.terminal_process.start(command)
        
    def handle_terminal_output(self):
        output = self.terminal_process.readAllStandardOutput().data().decode()
        self.terminal_output.appendPlainText(output)
        
    def handle_terminal_error(self):
        error = self.terminal_process.readAllStandardError().data().decode()
        self.terminal_output.appendPlainText(error)
        
    def run_current_file(self):
        if not self.current_file:
            self.terminal_output.appendPlainText("Error: No file is currently open")
            return
            
        self.save_file()
        content = ""
        for item in self.file_model.root['children']:
            content = self.get_file_content(item, self.current_file)
            if content is not None:
                break
    
        if content is None:
            self.terminal_output.appendPlainText("Error: Could not find file content")
            return
            
        self.terminal_output.clear()
        self.terminal_output.appendPlainText(f"Running {self.current_file}...\n")
        
        # Clear previous error indicators
        self.editor.line_number_area.set_errors([])
        self.editor.line_number_area.set_warnings([])
        
        try:
            import tempfile
            import platform
            is_windows = platform.system() == 'Windows'
            
            with tempfile.NamedTemporaryFile(mode='w', suffix=self.current_file[self.current_file.rfind('.'):], delete=False) as temp:
                cleaned_content = "\n".join(
                    line for line in content.split('\n') 
                    if not line.strip().startswith(':')
                )
                temp.write(cleaned_content)
                temp_path = temp.name
        
            file_ext = self.current_file[self.current_file.rfind('.'):].lower()
        
            if file_ext == '.py':
                command = ['python', temp_path]
                self.run_single_command(command, temp_path, file_ext)
            elif file_ext == '.js':
                command = ['node', temp_path]
                self.run_single_command(command, temp_path, file_ext)
            elif file_ext == '.java':
                # Compile first
                compile_cmd = ['javac', temp_path]
                self.terminal_output.appendPlainText(f"Compiling with: {' '.join(compile_cmd)}")
                
                compile_process = QProcess(self)
                compile_process.setProcessChannelMode(QProcess.MergedChannels)
                
                def handle_compile_output():
                    output = compile_process.readAllStandardOutput().data().decode()
                    self.terminal_output.appendPlainText(output)
                
                compile_process.readyReadStandardOutput.connect(handle_compile_output)
                
                def handle_compile_error():
                    error = compile_process.readAllStandardError().data().decode()
                    self.terminal_output.appendPlainText(error)
                    
                    # Parse error output to find line numbers and messages
                    error_lines, error_messages = self.parse_error_lines(error)
                    if error_lines:
                        self.editor.line_number_area.set_errors(error_lines, error_messages)
                
                compile_process.readyReadStandardError.connect(handle_compile_error)
                
                def handle_compile_finished(exit_code, exit_status):
                    if exit_code == 0:
                        # Compilation successful, run the program
                        class_name = os.path.basename(temp_path)[:-5]  # Remove .java extension
                        run_cmd = ['java', '-cp', os.path.dirname(temp_path), class_name]
                        self.terminal_output.appendPlainText(f"Running with: {' '.join(run_cmd)}")
                        self.run_single_command(run_cmd, temp_path, file_ext)
                    else:
                        self.terminal_output.appendPlainText(f"\nCompilation failed with exit code {exit_code}")
                
                compile_process.finished.connect(handle_compile_finished)
                compile_process.start(compile_cmd[0], compile_cmd[1:])
                
            elif file_ext in ('.c', '.cpp'):
                # Determine compiler and executable extension
                if file_ext == '.c':
                    compiler = 'gcc'
                else:  # .cpp
                    compiler = 'g++'
                    
                # Create executable path
                exe_ext = '.exe' if is_windows else ''
                exe_path = temp_path + exe_ext
                
                # Compile first
                compile_cmd = [compiler, temp_path, '-o', exe_path]
                self.terminal_output.appendPlainText(f"Compiling with: {' '.join(compile_cmd)}")
                
                compile_process = QProcess(self)
                compile_process.setProcessChannelMode(QProcess.MergedChannels)
                
                def handle_compile_output():
                    output = compile_process.readAllStandardOutput().data().decode()
                    self.terminal_output.appendPlainText(output)
                
                compile_process.readyReadStandardOutput.connect(handle_compile_output)
                
                def handle_compile_error():
                    error = compile_process.readAllStandardError().data().decode()
                    self.terminal_output.appendPlainText(error)
                    
                    # Parse error output to find line numbers and messages
                    error_lines, error_messages = self.parse_error_lines(error)
                    if error_lines:
                        self.editor.line_number_area.set_errors(error_lines, error_messages)
                
                compile_process.readyReadStandardError.connect(handle_compile_error)
                
                def handle_compile_finished(exit_code, exit_status):
                    if exit_code == 0:
                        # Compilation successful, run the program
                        run_cmd = [exe_path]
                        self.terminal_output.appendPlainText(f"Running with: {' '.join(run_cmd)}")
                        self.run_single_command(run_cmd, temp_path, file_ext, exe_path)
                    else:
                        self.terminal_output.appendPlainText(f"\nCompilation failed with exit code {exit_code}")
                
                compile_process.finished.connect(handle_compile_finished)
                compile_process.start(compile_cmd[0], compile_cmd[1:])
                
            else:
                self.terminal_output.appendPlainText(f"Error: Unsupported file type {file_ext}")
                return
        
        except Exception as e:
            self.terminal_output.appendPlainText(f"Error: {str(e)}")
            
    def run_single_command(self, command, temp_path, file_ext, exe_path=None):
        """Run a single command and handle its output"""
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)

        def handle_output():
            output = process.readAllStandardOutput().data().decode()
            self.terminal_output.appendPlainText(output)

        process.readyReadStandardOutput.connect(handle_output)

        def handle_error():
            error = process.readAllStandardError().data().decode()
            self.terminal_output.appendPlainText(error)
            
            # Parse error output to find line numbers and messages
            error_lines, error_messages = self.parse_error_lines(error)
            if error_lines:
                self.editor.line_number_area.set_errors(error_lines, error_messages)

        process.readyReadStandardError.connect(handle_error)

        def handle_finished(exit_code, exit_status):
            self.terminal_output.appendPlainText(f"\nProcess finished with exit code {exit_code}")
            try:
                os.unlink(temp_path)
                if exe_path and os.path.exists(exe_path):
                    os.unlink(exe_path)
                elif file_ext in ('.c', '.cpp'):
                    # Try to remove the executable with the expected extension
                    exe_ext = '.exe' if sys.platform.system() == 'Windows' else ''
                    expected_exe = temp_path + exe_ext
                    if os.path.exists(expected_exe):
                        os.unlink(expected_exe)
            except Exception as e:
                self.terminal_output.appendPlainText(f"Cleanup error: {str(e)}")

        process.finished.connect(handle_finished)
        process.start(command[0], command[1:])
            
    def parse_error_lines(self, error_output):
        """Parse error output to extract line numbers with errors"""
        error_lines = []
        error_messages = {}
        lines = error_output.split('\n')
        
        # Common patterns for error messages with line numbers
        patterns = [
            (r'File ".*", line (\d+): (.*)', 1, 2),  # group 1 is line, group 2 is message
            (r'.*\.py:(\d+): (.*)', 1, 2),
            (r'.*\.js:(\d+): (.*)', 1, 2),
            (r'.*\.java:(\d+): (.*)', 1, 2),
            (r'.*\.c:(\d+): (.*)', 1, 2),
            (r'.*\.cpp:(\d+): (.*)', 1, 2),
            (r'line (\d+): (.*)', 1, 2),
            (r'Line (\d+): (.*)', 1, 2),
        ]
        
        for line in lines:
            for pattern in patterns:
                match = re.search(pattern[0], line)
                if match:
                    try:
                        line_num = int(match.group(pattern[1]))
                        message = match.group(pattern[2])
                        error_lines.append(line_num)
                        error_messages[line_num] = message
                    except (ValueError, IndexError):
                        pass
                        
        return error_lines, error_messages
            
    def get_file_content(self, item, filename):
        if item['type'] == 'file' and item['name'] == filename:
            return item['content']
            
        if 'children' in item:
            for child in item['children']:
                content = self.get_file_content(child, filename)
                if content is not None:
                    return content
        return None

class CodeHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for multiple languages"""
    def __init__(self, document):
        super().__init__(document)
        self.language = None
        self.rules = {}
        
        self.init_python_rules()
        self.init_javascript_rules()
        self.init_c_cpp_rules()
        self.init_markdown_rules()
        
    def init_python_rules(self):
        python_keywords = [
            'and', 'as', 'assert', 'break', 'class', 'continue', 'def', 'del',
            'elif', 'else', 'except', 'False', 'finally', 'for', 'from', 'global',
            'if', 'import', 'in', 'is', 'lambda', 'None', 'nonlocal', 'not', 'or',
            'pass', 'raise', 'return', 'True', 'try', 'while', 'with', 'yield'
        ]
        
        self.rules['python'] = {
            'keywords': (python_keywords, COLORS['special'], QFont.Bold),
            'strings': ([r'\"[^\"\\]*(\\.[^\"\\]*)*\"', r"\'[^\'\\]*(\\.[^\'\\]*)*\'"], COLORS['yellow']),
            'numbers': (['\\b[0-9]+\\b'], COLORS['purple']),
            'comments': (['#[^\\n]*'], COLORS['comment'])
        }
        
    def init_javascript_rules(self):
        js_keywords = [
            'break', 'case', 'catch', 'class', 'const', 'continue', 'debugger',
            'default', 'delete', 'do', 'else', 'export', 'extends', 'finally',
            'for', 'function', 'if', 'import', 'in', 'instanceof', 'new',
            'return', 'super', 'switch', 'this', 'throw', 'try', 'typeof',
            'var', 'void', 'while', 'with', 'yield'
        ]
        
        self.rules['javascript'] = {
            'keywords': (js_keywords, COLORS['special'], QFont.Bold),
            'strings': ([r'\"[^\"\\]*(\\.[^\"\\]*)*\"', r"\'[^\'\\]*(\\.[^\'\\]*)*\'", r'\`[^\`\\]*(\\.[^\`\\]*)*\`'], COLORS['yellow']),
            'numbers': (['\\b[0-9]+\\b'], COLORS['purple']),
            'comments': (['//[^\\n]*', '/\\*.*?\\*/'], COLORS['comment'])
        }
        
    def init_c_cpp_rules(self):
        c_keywords = [
            'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do',
            'double', 'else', 'enum', 'extern', 'float', 'for', 'goto', 'if',
            'int', 'long', 'register', 'return', 'short', 'signed', 'sizeof', 'static',
            'struct', 'switch', 'typedef', 'union', 'unsigned', 'void', 'volatile', 'while'
        ]
        
        cpp_keywords = c_keywords + [
            'alignas', 'alignof', 'and', 'and_eq', 'asm', 'auto', 'bitand', 'bitor',
            'bool', 'break', 'case', 'catch', 'char', 'char8_t', 'char16_t', 'char32_t',
            'class', 'compl', 'concept', 'const', 'consteval', 'constexpr', 'const_cast',
            'continue', 'co_await', 'co_return', 'co_yield', 'decltype', 'default', 'delete',
            'do', 'double', 'dynamic_cast', 'else', 'enum', 'explicit', 'export', 'extern',
            'false', 'float', 'for', 'friend', 'goto', 'if', 'inline', 'int', 'long',
            'mutable', 'namespace', 'new', 'noexcept', 'not', 'not_eq', 'nullptr', 'operator',
            'or', 'or_eq', 'private', 'protected', 'public', 'register', 'reinterpret_cast',
            'requires', 'return', 'short', 'signed', 'sizeof', 'static', 'static_assert',
            'static_cast', 'struct', 'switch', 'template', 'this', 'thread_local', 'throw',
            'true', 'try', 'typedef', 'typeid', 'typename', 'union', 'unsigned', 'using',
            'virtual', 'void', 'volatile', 'wchar_t', 'while', 'xor', 'xor_eq'
        ]
        
        self.rules['c'] = {
            'keywords': (c_keywords, COLORS['special'], QFont.Bold),
            'types': (['void', 'char', 'short', 'int', 'long', 'float', 'double', 'signed', 'unsigned'], COLORS['blue']),
            'strings': ([r'\"[^\"\\]*(\\.[^\"\\]*)*\"'], COLORS['yellow']),
            'numbers': (['\\b[0-9]+\\b'], COLORS['purple']),
            'comments': (['//[^\\n]*', '/\\*.*?\\*/'], COLORS['comment']),
            'preprocessor': (['#.*'], COLORS['info'])
        }
        
        self.rules['cpp'] = {
            'keywords': (cpp_keywords, COLORS['special'], QFont.Bold),
            'types': (['void', 'char', 'short', 'int', 'long', 'float', 'double', 'signed', 'unsigned', 
                       'bool', 'wchar_t', 'char8_t', 'char16_t', 'char32_t'], COLORS['blue']),
            'strings': ([r'\"[^\"\\]*(\\.[^\"\\]*)*\"'], COLORS['yellow']),
            'numbers': (['\\b[0-9]+\\b'], COLORS['purple']),
            'comments': (['//[^\\n]*', '/\\*.*?\\*/'], COLORS['comment']),
            'preprocessor': (['#.*'], COLORS['info'])
        }
        
    def init_markdown_rules(self):
        self.rules['markdown'] = {
            'bold': ([r'\*\*.*?\*\*', r'__.*?__'], COLORS['fg'], QFont.Bold),
            'italic': ([r'\*.*?\*', r'_.*?_'], COLORS['fg'], None, True),
            'code': ([r'`.*?`'], COLORS['yellow']),
            'links': ([r'\[.*?\]\(.*?\)'], COLORS['blue'])
        }
        
    def set_document_language(self, filename):
        if filename.endswith('.py'):
            self.language = 'python'
        elif filename.endswith(('.js', '.jsx', '.ts', '.tsx')):
            self.language = 'javascript'
        elif filename.endswith('.c'):
            self.language = 'c'
        elif filename.endswith(('.cpp', '.cc', '.cxx', '.c++', '.hpp', '.hxx')):
            self.language = 'cpp'
        elif filename.endswith(('.md', '.markdown')):
            self.language = 'markdown'
        else:
            self.language = None
            
    def highlightBlock(self, text):
        if not self.language or self.language not in self.rules:
            return
            
        rules = self.rules[self.language]
        
        for rule in rules.values():
            patterns, color, *format_args = rule
            if not isinstance(patterns, list):
                patterns = [patterns]
                
            format = QTextCharFormat()
            format.setForeground(QColor(color))
            if format_args:
                if len(format_args) > 0 and isinstance(format_args[0], int):
                    format.setFontWeight(format_args[0])
                if len(format_args) > 1 and isinstance(format_args[1], bool):
                    format.setFontItalic(format_args[1])
            
            for pattern in patterns:
                try:
                    expression = re.compile(pattern)
                    for match in expression.finditer(text):
                        start, end = match.span()
                        self.setFormat(start, end - start, format)
                except re.error as e:
                    print(f"Regex error in pattern '{pattern}': {str(e)}")
                continue

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for a modern look
    
    # Set application font
    font = QFont("JetBrains Mono", 10)
    app.setFont(font)
    
    editor = VimAIEditor()
    editor.show()
    sys.exit(app.exec_())