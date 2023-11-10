```mermaid
flowchart TD;
    useq((useq))
    pymmcore-plus((pymmcore-plus))
    pymmcore-widgets((pymmcore-widgets))
    iSIMEngine{iSIMEngine}
    control.gui{control.gui}
    iSIMRunner{iSIMRunner \n iSIMSettings}

    devices{devices}
    NIDAQ[[NIDAQ]]
    nidaqmx((nidaqmx))

    %% Acquisisitons
    useq --> MDASequence
    pymmcore-widgets --> MDAWidget
    control.gui --> AcquisitionSettings
    AcquisitionSettings --> iSIMRunner
    MDAWidget --> AcquireButton
    AcquireButton --> iSIMRunner
    MDAWidget --> useq

    MDASequence --> iSIMRunner
    pymmcore-plus --> MDARunner

    iSIMRunner -- acq_clicked \n MDASequence--> MDARunner
    iSIMRunner -- settings['ni'] --> devices

    MDARunner -- MDAEvent, \n MDASequence --> iSIMEngine
    iSIMEngine -- MDASequence --> setup_sequence
    iSIMEngine --> exec_event
    iSIMEngine -- MDAEvent --> setup_event
    devices --> setup_event
    setup_event --> ni_data
    setup_event --> snap
    ni_data -.-> exec_event
    exec_event --> nidaqmx
    nidaqmx --> NIDAQ
    snap --> StackViewer
    snap --> OMETiffWriter


    %% Live Mode
    pymmcore-widgets --> LiveButton
    LiveButton --> iSIMRunner
    LiveEngine{LiveEngine} --> nidaqmx
    LiveEngine --> snap
    NIDAQ --> snap
    snap --> LiveViewer

    devices --> LiveEngine
    iSIMRunner -- settings['live'] \n live_clicked--> LiveEngine

    control.gui --> LiveSettings
    pymmcore-widgets --> control.gui
    LiveSettings --> iSIMRunner

```