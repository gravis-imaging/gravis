// import * as cornerstone_test from './static/cornerstone/bundle.js';
// import { Cornerstone } from './static/cornerstone/bundle.js';
// console.log(Cornerstone)

async function cacheMetadata({
    StudyInstanceUID,
    SeriesInstanceUID,
    wadoRsRoot,
    type,
  }){
    const studySearchOptions = {
        studyInstanceUID: StudyInstanceUID,
        seriesInstanceUID: SeriesInstanceUID,
    };

    const client = new dicomweb.DICOMwebClient({ url: wadoRsRoot });
    const instances = await client.retrieveSeriesMetadata(studySearchOptions);
    console.log(instances)
}

function createTools( volumeId ) {
    const cornerstoneTools = window.cornerstone.tools;
    const {
        PanTool,
        WindowLevelTool,
        StackScrollMouseWheelTool,
        ZoomTool,
        ToolGroupManager,
        Enums: csToolsEnums,
    } = cornerstoneTools;
    const { MouseBindings } = csToolsEnums;

    const toolGroupId = 'STACK_TOOL_GROUP_ID';

    // Add tools to Cornerstone3D
    cornerstoneTools.addTool(PanTool);
    cornerstoneTools.addTool(WindowLevelTool);
    cornerstoneTools.addTool(StackScrollMouseWheelTool);
    cornerstoneTools.addTool(ZoomTool);
    // Define a tool group, which defines how mouse events map to tool commands for
    // Any viewport using the group
    const toolGroup = ToolGroupManager.createToolGroup(toolGroupId);

    // Add tools to the tool group
    toolGroup.addTool(WindowLevelTool.toolName, { volumeId } );
    toolGroup.addTool(PanTool.toolName,  { volumeId } );
    toolGroup.addTool(ZoomTool.toolName,  { volumeId } );
    toolGroup.addTool(StackScrollMouseWheelTool.toolName, { volumeId });

    // Set the initial state of the tools, here all tools are active and bound to
    // Different mouse inputs
    toolGroup.setToolActive(WindowLevelTool.toolName, {
    bindings: [
        {
        mouseButton: MouseBindings.Primary, // Left Click
        },
    ],
    });
    toolGroup.setToolActive(PanTool.toolName, {
    bindings: [
        {
        mouseButton: MouseBindings.Auxiliary, // Middle Click
        },
    ],
    });
    toolGroup.setToolActive(ZoomTool.toolName, {
    bindings: [
        {
        mouseButton: MouseBindings.Secondary, // Right Click
        },
    ],
    });
    // As the Stack Scroll mouse wheel is a tool using the `mouseWheelCallback`
    // hook instead of mouse buttons, it does not need to assign any mouse button.
    toolGroup.setToolActive(StackScrollMouseWheelTool.toolName);
    return toolGroup;
}

async function run() {
    const { RenderingEngine, Types, Enums, volumeLoader, CONSTANTS, setVolumesForViewports} = window.cornerstone;

    
    const { ViewportType } = Enums;
    const { ORIENTATION } = CONSTANTS;

    const volumeName = 'CT_VOLUME_ID'; // Id of the volume less loader prefix
    const volumeLoaderScheme = 'cornerstoneStreamingImageVolume'; // Loader id which defines which volume loader to use
    const volumeId = `${volumeLoaderScheme}:${volumeName}`; // VolumeId with loader id + volume id

    const content = document.getElementById('content');
    const element = document.createElement('div');
    element.id = 'cornerstone-element';
    element.style.width = '500px';
    element.style.height = '500px';

    content.appendChild(element);

    await cornerstone.helpers.initDemo();


    // Get Cornerstone imageIds and fetch metadata into RAM
    var imageIds = await cornerstone.helpers.createImageIdsAndCacheMetaData({
        StudyInstanceUID:
        '1.3.6.1.4.1.5962.99.1.1647423216.1757746261.1397511827184.6.0',
        SeriesInstanceUID:
        '1.3.6.1.4.1.5962.99.1.1647423216.1757746261.1397511827184.7.0',
        wadoRsRoot: 'http://localhost:9090/wado',
        type: 'VOLUME',
    });
    // streaming-wadors requests the raw image data only, but our WADO implementation doesn't support that.
    // Instead, use WADO-URI which expects entire DICOM files. 
    for (var k=0; k < imageIds.length; k++){
        imageIds[k] = "wadouri:" + imageIds[k].slice(17)
    }
    console.log(imageIds)

    // var imageIds = []
    // for (var k=0; k<=30; k = k+1) {
    //     imageIds.push('wadouri:http://localhost:9090/media/pineapple/1429657203_SAGPD_' + k.toString().padStart(3, 0) + '.dcm')
    // }
    // for (var k=0; k<=22; k = k+1) {
    //     imageIds.push('wadouri:http://localhost:9090/media/phantom-volume/IM' + k.toString().padStart(5, 0) + '')
    // }

    // let fakeProvider = {
    //     get: function (type, imageID) {
    //         console.log("Get", type, imageID);
    //         return {
    //             pixelRepresentation: 1,
    //             bitsAllocated: 16,
    //             bitsStored: 12,
    //             imageOrientationPatient: [1, 0, 0, 0, 1, 0],
    //             imagePositionPatient: [ 0,0, 3.*parseInt(imageID.slice(-7,-4))],
    //             pixelSpacing: [0.364583333333,0.364583333333],
    //             highBit: 11,
    //             photometricInterpretation: "MONOCHROME2",
    //             samplesPerPixel: 1,
    //             columns: 384,
    //             rows: 384
    //         }
    //     }
    // }
    // cornerstone.metaData.addProvider(
    //     fakeProvider.get.bind(fakeProvider),
    //     100
    // );

    // Instantiate a rendering engine
    const renderingEngineId = 'myRenderingEngine';
    const renderingEngine = new RenderingEngine(renderingEngineId);

    // Create a stack viewport
    const viewportId = 'CT_STACK';
    const viewportInput = {
        viewportId,
    //   type: Enums.ViewportType.STACK,
        type: ViewportType.ORTHOGRAPHIC,
        element,
        defaultOptions: {
            orientation: {
            // Random oblique orientation
            viewUp: [
                -0.5962687530844388, 0.5453181550345819, -0.5891448751239446,
            ],
            sliceNormal: [
                -0.5962687530844388, 0.5453181550345819, -0.5891448751239446,
            ],
            },
            background: [0.2, 0, 0.2],
        },
    };

    renderingEngine.enableElement(viewportInput);
    
    var toolGroup = createTools(volumeId)
    toolGroup.addViewport(viewportId, renderingEngineId);
    // Get the stack viewport that was created
    const viewport = (
        renderingEngine.getViewport(viewportId)
    );

    const volume = await volumeLoader.createAndCacheVolume(volumeId, {
        imageIds,
    });
    volume.load();
    // const stack = imageIds;

    // Set the stack on the viewport
    viewport.setVolumes([
        { volumeId },
    ]);
    // await viewport.setStack(stack);

    // Set the VOI of the stack
    // viewport.setProperties({ voiRange:{lower:0, upper:255} });
    setVolumesForViewports(renderingEngine, [{ volumeId }], [viewportId]);
    // Render the image
    viewport.render();
}

window.onload = async function() {
    await run()
}