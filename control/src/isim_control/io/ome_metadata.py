""" File to first try to make out own metadata """
import ome_types
from useq import MDAEvent, MDASequence, Channel
import numpy as np
from datetime import datetime
import json
from typing import List

from ome_types.model import simple_types


ome_model = ome_types.model


class OME:
    """OME Metadata class based on ome_types

    This class can be used to generate OME metadata during an acquisition using the EDA plugin. The
    writer implemented uses this and the methods to generate the metadata as the images come in.
    """
    def __init__(self, ome=ome_model.OME, seq: MDASequence|None = None):
        # TODO: Make this version to be taken over from the setup.py file
        self.ome = ome(creator="LEB, iSIM, V0.0.1")
        self.instrument_ref = ome_model.InstrumentRef(id="Instrument:0")
        # TODO: This we should get also in the settings
        self.stage_label = ome_model.StageLabel(
            name="Default", x=0.0, x_unit="µm", y=0.0, y_unit="µm"
        )

        self.seq = seq
        self.acquisition_date = str(datetime.now())
        self.max_indices = [1, 1, 1]
        self.planes = []
        self.tiff_data = []

    def add_plane_from_image(self, _, event: MDAEvent, meta:dict):
        """The units are hardcoded for now."""
        plane = ome_model.Plane(
            exposure_time=event.exposure,
            exposure_time_unit="ms",
            the_c=event.index.get("c", 0),
            the_z=event.index.get("z", 0),
            the_t=event.index.get("t", 0),
            delta_t=meta.get('ElapsedTime-ms',0.0),
            delta_t_unit="ms",
            position_x=event.x_pos,
            position_x_unit="µm",
            position_y=event.y_pos,
            position_y_unit="µm",
            position_z=event.z_pos,
            position_z_unit="µm",
        )
        tiff = ome_model.TiffData(
            first_c=event.index.get("c", 0),
            first_t=event.index.get("t", 0),
            first_z=event.index.get("z", 0),
            ifd=len(self.planes),
            plane_count=1,
        )
        # self.image_size = image.raw_image.shape
        self.max_indices = [
            max(self.max_indices[0], event.index.get("c", 0) + 1),
            max(self.max_indices[1], event.index.get("t", 0) + 1),
            max(self.max_indices[2], event.index.get("z", 0) + 1),
        ]
        self.planes.append(plane)
        self.tiff_data.append(tiff)

    def finalize_metadata(self):
        """No more images to be expected, set the values for all images received so far."""
        pixels = self.pixels_after_acqusition()
        images = [
            ome_model.Image(id="Image:0", pixels=pixels, acquisition_date=self.acquisition_date)
        ]
        self.ome.images = images
        print("OME Metadata generated")

    def pixels_after_acqusition(self) -> ome_model.Pixels:
        """Generate the Pixels instance after all images where acquired and received."""
        dim_order = [a for a in self.seq.axis_order if a.upper() in "ZCT"] + ["Y","X"]
        dim_order = "".join(dim_order).upper()
        dim_order = dim_order[::-1]
        pixels = ome_model.Pixels(
            id="Pixels:0",
            dimension_order=dim_order,
            size_c=self.max_indices[0],
            size_t=self.max_indices[1],
            size_z=self.max_indices[2],
            size_x=self.image_size[0],
            size_y=self.image_size[1],
            type=simple_types.PixelType("uint16"), #TODO: get this from meta
            big_endian=False,
            physical_size_x=1.0,
            physical_size_x_unit=simple_types.UnitsLength("µm"),
            physical_size_y=1.0,
            physical_size_y_unit=simple_types.UnitsLength("µm"),
            physical_size_z=0.5,
            physical_size_z_unit=simple_types.UnitsLength("µm"),
            channels=self.channels,
            planes=self.planes,
            tiff_data_blocks=self.tiff_data,
        )
        return pixels

    def init_from_sequence(self, seq:MDASequence):
        """Initialize OME from MMSettings translated from Micro-Manager settings from java."""
        self.seq = seq
        self.channels = self.channels_from_seq(seq.channels)
        # self.ome.instrument = self.instrument_from_settings(settings.microscope)

    def instrument_from_settings(self, microscope):
        """Generate the instrument from the information received from Micro-Manager."""
        instrument = ome_model.Instrument(
            id="Instrument:0",
            detectors=[self.detector_from_settings(microscope.detector)],
            microscope=self.microscope_from_settings(microscope),
        )
        return instrument

    def channels_from_seq(self, channels: [Channel]):
        """Generate the channels from the channel information received from Micro-Manager."""
        ome_channels = []
        for idx, channel in enumerate(channels):
            ome_channel = ome_model.Channel(
                id="Channel:0:" + str(idx),
                name=channel.config,
                #color=simple_types.Color(),  # TODO implement to take colors over
                samples_per_pixel=1,  # TODO check if this is correct
            )
            ome_channels.append(ome_channel)

        return ome_channels

    def detector_from_settings(self, detector):
        """Generate the detector from the information received from Micro-Manager."""
        return ome_model.Detector(
            id=detector.id,
            manufacturer=detector.manufacturer,
            model=detector.model,
            serial_number=detector.serial_number,
            offset=detector.offset,
        )

    def microscope_from_settings(self, microscope):
        """ Generate the microscope from the information received from Micro-Manager."""
        return ome_model.Microscope(manufacturer=microscope.manufacturer, model=microscope.model)


if __name__ == "__main__":

    from isim_control.io.ome_tiff_writer import OMETiffWriter
    from isim_control.settings import iSIMSettings
    import tifffile
    # metadata_string = '{"PositionName":"Default","PixelSizeAffine":"AffineTransform[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]","UserData":{"PseudoChannel-useChannels":"Off","PseudoChannel-useSlices":"Off","PseudoChannel-Slices":"1","PseudoChannel-Channels":"1"},"ReceivedTime":"2022-08-12 15:59:07.413 +0200","ROI":"java.awt.Rectangle[x=0,y=0,width=512,height=512]","BitDepth":"16","ElapsedTimeMs":"419.0","ZPositionUm":"0.0","Binning":"1","ExposureMs":"100.0","ScopeData":{"Z-Description":"Demo stage driver","Camera-PixelType":"16bit","Camera-Binning":"1","Core-Shutter":"Shutter","Camera-FastImage":"0","Z-Name":"DStage","Camera-SimulateCrash":"","Emission-Name":"DWheel","Camera-TransposeMirrorX":"0","Camera-TransposeMirrorY":"0","Shutter-State":"0","Camera-Mode":"Artificial Waves","Core-AutoShutter":"1","Z-Position":"0.0000","Camera-UseExposureSequences":"No","Dichroic-State":"0","Dichroic-Name":"DWheel","Path-Description":"Demo light-path driver","Path-Name":"DLightPath","Camera-Description":"Demo Camera Device Adapter","Dichroic-Description":"Demo filter wheel driver","Camera-ReadNoise (electrons)":"2.5000","Camera-RotateImages":"0","Dichroic-HubID":"","Camera-BitDepth":"16","Camera-DisplayImageNumber":"0","Camera-FractionOfPixelsToDropOrSaturate":"0.0020","Core-ChannelGroup":"Channel","Camera-AsyncPropertyLeader":"","Path-HubID":"","Excitation-Name":"DWheel","Camera-OnCameraCCDYSize":"512","Core-ImageProcessor":"","Core-Camera":"Camera","Camera-CameraID":"V1.0","XY-TransposeMirrorX":"0","Objective-State":"1","XY-TransposeMirrorY":"0","XY-Name":"DXYStage","Camera-MultiROIFillValue":"0","Camera-AsyncPropertyDelayMS":"2000","Excitation-Description":"Demo filter wheel driver","Camera-SaturatePixels":"0","Autofocus-Description":"Demo auto-focus adapter","Camera-Name":"DCam","Excitation-HubID":"","Camera-TransposeXY":"0","Camera-CCDTemperature":"0.0000","Camera-Gain":"0","Autofocus-HubID":"","Shutter-HubID":"","Camera-TestProperty1":"0.0000","Camera-DropPixels":"0","Camera-TestProperty2":"0.0000","Camera-TestProperty3":"0.0000","Autofocus-Name":"DAutoFocus","Camera-TestProperty4":"0.0000","Z-UseSequences":"No","Camera-TestProperty5":"0.0000","Camera-TestProperty6":"0.0000","Emission-ClosedPosition":"0","Shutter-Description":"Demo shutter driver","Core-Initialize":"1","XY-HubID":"","Emission-State":"0","Emission-Description":"Demo filter wheel driver","Core-AutoFocus":"Autofocus","Z-HubID":"","Camera-CameraName":"DemoCamera-MultiMode","Objective-Label":"Nikon 10X S Fluor","Camera-ScanMode":"1","Camera-TransposeCorrection":"0","Camera-AsyncPropertyFollower":"","Core-TimeoutMs":"5000","Objective-HubID":"","Dichroic-ClosedPosition":"0","Shutter-Name":"DShutter","XY-Description":"Demo XY stage driver","Camera-Exposure":"100.00","Core-Galvo":"","Camera-MaximumExposureMs":"10000.0000","Camera-ReadoutTime":"0.0000","Camera-Photon Conversion Factor":"1.0000","Dichroic-Label":"400DCLP","Emission-HubID":"","Camera-HubID":"","Camera-Photon Flux":"50.0000","Camera-TriggerDevice":"","Excitation-State":"0","Core-XYStage":"XY","Path-Label":"State-0","Excitation-ClosedPosition":"0","Camera-AllowMultiROI":"0","Emission-Label":"Chroma-HQ700","Objective-Name":"DObjective","Excitation-Label":"Chroma-HQ570","Core-SLM":"","Path-State":"0","Objective-Trigger":"-","Camera-CCDTemperature RO":"0.0000","Camera-Offset":"0","Core-Focus":"Z","Camera-OnCameraCCDXSize":"512","Objective-Description":"Demo objective turret driver","Camera-StripeWidth":"1.0000"},"XPositionUm":"0.0","PixelSizeUm":"1.0","Class":"class org.micromanager.data.internal.DefaultMetadata","Camera":"Camera","UUID":"798e1008-c618-4ca8-b3f5-0c0212a858aa","YPositionUm":"0.0"}'
    # metadata_dict = json.loads(metadata_string)

    seq = MDASequence(channels = ({"config": "DAPI", "exposure":10},
                                  {"config": "FITC", "exposure":10}),
                    #   grid_plan={"rows":2, "columns":2},
                      time_plan={"interval":0.15, "loops":10},
                      z_plan={"bottom":0, "top":2, "step":1},)
    from pymmcore_plus import CMMCorePlus
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration()

    ome = OME()
    ome.init_from_sequence(seq)
    ome.image_size = (512, 512)
    mmc.mda.events.sequenceStarted.connect(ome.init_from_sequence)
    mmc.mda.events.frameReady.connect(ome.add_plane_from_image)
    mmc.mda.events.sequenceFinished.connect(ome.finalize_metadata)

    mm_config = mmc.getSystemState().dict()
    settings = iSIMSettings()
    writer = OMETiffWriter("C:/Users/stepp/Desktop", settings, mm_config)
    writer.sequenceStarted(seq)
    mmc.mda.events.frameReady.connect(writer.frameReady)


    mmc.mda.run(seq)

    print(json.dumps(ome.ome.to_xml(), indent=4))
    tifffile.tiffcomment("C:/Users/stepp/Desktop/Desktop.ome.tiff", ome.ome.to_xml().encode())

    # print(json.dumps(metadata_dict, indent=4))
