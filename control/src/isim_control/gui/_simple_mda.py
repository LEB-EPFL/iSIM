from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QSizePolicy, QWidget,
                            QGroupBox, QGridLayout, QSpinBox, QVBoxLayout, QFormLayout,
                            QLineEdit, QCheckBox)
from pymmcore_widgets.mda._core_z import CoreConnectedZPlanWidget
from pymmcore_widgets._mda._general_mda_widgets import _AcquisitionOrderWidget, _MDAControlButtons
from datetime import timedelta
from superqt import QQuantity

from useq import MDASequence, TIntervalLoops

class SimpleMDAWidget(QWidget):
    """Simple MultiDataAcquisition Widget.

    Simpler MDA widget."""

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent=parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        self.setLayout(QGridLayout())

        self.timeBox = QGroupBox("Time Points")
        self.timeBox.setLayout(QFormLayout())
        self.timeBox.setCheckable(True)
        self.timeBox.setChecked(True)
        self.timepoints = QSpinBox()
        self.timepoints.setRange(1, 100000)
        self.timepoints.setValue(1)
        self.timeBox.layout().addRow("Count", self.timepoints)
        self.interval = QHBoxLayout()
        self.interval_val = QLineEdit()
        self.interval.addWidget(self.interval_val)
        self.interval_unit = QComboBox()
        self.interval_unit.addItem('ms')
        self.interval_unit.addItem('s')
        self.interval_unit.addItem('min')
        self.interval_unit.setCurrentIndex(1)
        self.interval.addWidget(self.interval_unit)
        self.timeBox.layout().addRow("Interval", self.interval)

        self.layout().addWidget(self.timeBox, 0, 0)

        self.slices = QGroupBox("Z Slices")
        self.slices.setCheckable(True)
        self.slices.setChecked(True)
        self.slices.setLayout(QVBoxLayout())
        self.stack_widget = CoreConnectedZPlanWidget()
        self.slices.layout().addWidget(self.stack_widget)
        self.layout().addWidget(self.slices, 1, 0, 1, 2)

        channels = QGroupBox("Channels")
        channels.setCheckable(True)
        channels.setChecked(True)
        channels.setLayout(QFormLayout())
        self.channel_488 = QCheckBox()
        self.channel_561 = QCheckBox()
        channels.layout().addRow("488", self.channel_488)
        channels.layout().addRow("561", self.channel_561)
        self.layout().addWidget(channels, 0, 1)

        self.acq_order = _AcquisitionOrderWidget()
        self.layout().addWidget(self.acq_order, 2, 0, 1, 2)


        self.buttons_wdg = _MDAControlButtons()
        self.buttons_wdg.run_button.clicked.connect(self._on_run_clicked)
        self.buttons_wdg.run_button.show()
        self.buttons_wdg.pause_button.released.connect(self._mmc.mda.toggle_pause)
        self.buttons_wdg.cancel_button.released.connect(self._mmc.mda.cancel)
        self.layout().addWidget(self.buttons_wdg)

    def get_state(self) -> MDASequence:
        interval = QQuantity(self.interval_val.text() + self.interval_unit.currentText())
        if self.timeBox.isChecked():
            time_plan = TIntervalLoops(interval=interval.value().to_timedelta(),
                                    loops=self.timepoints.value())
        else:
            time_plan = None
        channels = ()
        if self.channel_488.isChecked():
            channels = channels + ('488',)
        if self.channel_561.isChecked():
            channels = channels + ('561',)
        mda = MDASequence(z_plan=self.stack_widget.value() if self.slices.isChecked() else None,
                          time_plan=time_plan,
                          channels=channels,
                          axis_order=self.acq_order.acquisition_order_comboBox.currentText()
            )
        return mda

    def set_state(self, seq: MDASequence) -> None:
        self.timeBox.setChecked(seq.time_plan is not None)
        if seq.time_plan is not None:
            self.timepoints.setValue(seq.time_plan.loops)
            self.interval_val.setText(str(seq.time_plan.interval.seconds))
            self.interval_unit.setCurrentText('s')
        self.slices.setChecked(seq.z_plan is not None)
        if seq.z_plan is not None:
            self.stack_widget.setValue(seq.z_plan)
        my_channels = [name.config for name in seq.channels]
        self.channel_488.setChecked('488' in my_channels)
        self.channel_561.setChecked('561' in my_channels)
        print(seq.axis_order)
        print(''.join(seq.axis_order))
        self.acq_order.acquisition_order_comboBox.setCurrentText(''.join(seq.axis_order))

    def _on_run_clicked(self):
        """Run the MDA sequence experiment."""
        # construct a `useq.MDASequence` object from the values inserted in the widget
        experiment = self.get_state()
        # run the MDA experiment asynchronously
        self._mmc.run_mda(experiment)
        return