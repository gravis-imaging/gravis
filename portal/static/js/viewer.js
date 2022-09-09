// import * as cornerstone_test from './static/cornerstone/bundle.js';
// import { Cornerstone } from './static/cornerstone/bundle.js';
// console.log(Cornerstone)

async function cacheMetadata({
    StudyInstanceUID,
    SeriesInstanceUID,
    wadoRsRoot,
  }){
    const SOP_INSTANCE_UID = '00080018';
    const SERIES_INSTANCE_UID = '0020000E';  
    const studySearchOptions = {
        studyInstanceUID: StudyInstanceUID,
        seriesInstanceUID: SeriesInstanceUID,
    };

    const client = new dicomweb.DICOMwebClient({ url: wadoRsRoot });
    const instances = await client.retrieveSeriesMetadata(studySearchOptions);
    imageIds = []
    for (var instanceMetaData of instances) {
        const SeriesInstanceUID = instanceMetaData[SERIES_INSTANCE_UID].Value[0];
        const SOPInstanceUID = instanceMetaData[SOP_INSTANCE_UID].Value[0];
    
        const prefix = 'wadouri:'
    
        const imageId =
          prefix +
          wadoRsRoot +
          '/studies/' +
          StudyInstanceUID +
          '/series/' +
          SeriesInstanceUID +
          '/instances/' +
          SOPInstanceUID +
          '/frames/1';
    
        cornerstone.cornerstoneWADOImageLoader.wadors.metaDataManager.add(
          imageId,
          instanceMetaData
        );
        imageIds.push(imageId);
    }
    return imageIds;
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

async function run(study_uid, series_uid) {
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
    var imageIds = await cacheMetadata({
        StudyInstanceUID: study_uid,
        // '1.3.6.1.4.1.5962.99.1.1647423216.1757746261.1397511827184.6.0',
        SeriesInstanceUID: series_uid,
        // '1.3.6.1.4.1.5962.99.1.1647423216.1757746261.1397511827184.7.0',
        wadoRsRoot: 'http://localhost:9090/wado',
    });

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

// window.onload = async function() {
//     await run()
// }