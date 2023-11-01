from qtpy.QtWidgets import QApplication
from qtpy.QtGui import QPalette, QColor
from qtpy.QtCore import Qt

def set_dark(app: QApplication):
    app.setStyle("Fusion")
    #
    # # Now use a palette to switch to dark colors:
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.Active, QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
    dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, Qt.darkGray)
    dark_palette.setColor(QPalette.Disabled, QPalette.Text, Qt.darkGray)
    dark_palette.setColor(QPalette.Disabled, QPalette.Light, QColor(53, 53, 53))
    app.setPalette(dark_palette)


def slider_theme(groove_color: str = "#990000"):
    return     """QSlider::groove:horizontal:enabled {
    border: 1px solid #000000;
    height: 1px; /* the groove expands to the size of the slider by default. by giving it a height, it has a fixed size */
    border-radius: 2 px;
    margin: 2 px 0 px;
    }

    QSlider::add-page:horizontal:enabled {
        background: #353535;
    }

    QSlider::sub-page:horizontal:enabled {
        background: green;
    }

    QSlider::handle:horizontal:enabled {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #535353, stop:1 #535353);
        border: 1px solid #535353;
        width: 10px;
        margin: -6px 0; /* handle is placed by default on the contents rect of the groove. Expand outside the groove */
        border-radius: 3px;
    }
    """
