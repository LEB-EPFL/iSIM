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

from pathlib import Path
handle_loc = Path(__file__).parent.resolve()/"assets/handle.png"

def slider_theme(groove_color: str = "red"):
    return     """QSlider::groove:horizontal {
    height: 5px; /* the groove expands to the size of the slider by default. by giving it a height, it has a fixed size */
    border-radius: 2 px;
    margin: 0 px 0 px;
    }

    QSlider::add-page:horizontal:enabled {
        background: #353535;
        border: 1px solid #252525;
    }

    QSlider::sub-page:horizontal:enabled {
        background: """+ groove_color + """;
        border: 1px solid #252525;
    }

    QSlider::add-page:horizontal:!enabled {
        background: #353535;
        border: 1px solid #252525;
    }

    QSlider::sub-page:horizontal:!enabled{
        background: #535353;
        border: 1px solid #252525;
    }

    QSlider::handle:horizontal {
        border-image: url("""+handle_loc.as_posix()+""");
        width: 17px;
        height: 15px;
        margin: -7px 0;
        }
    """
    # QSlider::handle:horizontal {
    #     background: qradialgradient(cx: .5, cy: .5, radius: 4, fx: .5, fy: .5, stop: 0 #535353, stop: 2 #535353, stop: 2 #FFFFFF);
    #     border: 1px solid #252525;
    #     margin: -4px 0; /* handle is placed by default on the contents rect of the groove. Expand outside the groove */
    #     width: 11px;
    #     height: 11px;
    #     border-radius: 3px;
