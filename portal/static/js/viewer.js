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

function createTools() {
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

    const toolGroupId = `STACK_TOOL_GROUP_ID`;
    
    // Add tools to Cornerstone3D
    cornerstoneTools.addTool(PanTool);
    cornerstoneTools.addTool(WindowLevelTool);
    cornerstoneTools.addTool(StackScrollMouseWheelTool);
    cornerstoneTools.addTool(ZoomTool);
    // Define a tool group, which defines how mouse events map to tool commands for
    // Any viewport using the group
    const toolGroup = ToolGroupManager.createToolGroup(toolGroupId);

    // Add tools to the tool group
    toolGroup.addTool(WindowLevelTool.toolName );
    toolGroup.addTool(PanTool.toolName );
    toolGroup.addTool(ZoomTool.toolName );
    toolGroup.addTool(StackScrollMouseWheelTool.toolName );

    // toolGroup.addTool(WindowLevelTool.toolName, { volumeId } );
    // toolGroup.addTool(PanTool.toolName,  { volumeId } );
    // toolGroup.addTool(ZoomTool.toolName,  { volumeId } );
    // toolGroup.addTool(StackScrollMouseWheelTool.toolName, { volumeId });


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


    const content = document.getElementById('content');
    const element = document.createElement('div');
    element.id = 'cornerstone-element';
    element.style.width = '500px';
    element.style.height = '500px';

    content.appendChild(element);

    await cornerstone.helpers.initDemo(); 

    // Instantiate a rendering engine
    const renderingEngineId = 'gravisRenderEngine';
    const renderingEngine = new RenderingEngine(renderingEngineId);

    // Create a stack viewport
    const viewportId = 'GRASP_VIEW';
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
    
    var toolGroup = createTools()
    toolGroup.addViewport(viewportId, renderingEngineId);
    // Get the stack viewport that was created
    const viewport = (
        renderingEngine.getViewport(viewportId)
    );

    // await viewport.setStack(stack);
    // setVolume()
    // Set the VOI of the stack
    // viewport.setProperties({ voiRange:{lower:0, upper:255} });
    // Render the image
    viewport.render();
}

async function setVolume(study_uid, series_uid) {
    const volumeName = series_uid; // Id of the volume less loader prefix
    const volumeLoaderScheme = 'cornerstoneStreamingImageVolume'; // Loader id which defines which volume loader to use
    const volumeId = `${volumeLoaderScheme}:${volumeName}`; // VolumeId with loader id + volume id

    // Get Cornerstone imageIds and fetch metadata into RAM
    var imageIds = await cacheMetadata({
        StudyInstanceUID: study_uid,
        SeriesInstanceUID: series_uid,
        wadoRsRoot: '/wado',
    });

    const volume = await cornerstone.volumeLoader.createAndCacheVolume(volumeId, {
        imageIds,
    });
    volume.load();
    // const stack = imageIds;
    const renderingEngine = window.cornerstone.getRenderingEngine(
        'gravisRenderEngine'
      );
  
    const viewport = (
        renderingEngine.getViewport('GRASP_VIEW')
    );
    // Set the stack on the viewport
    viewport.setVolumes([
        { volumeId },
    ]);
    // setVolumesForViewports(renderingEngine, [{ volumeId }], [viewportId]);

    viewport.render();
}
window.onload = async function() {
    await run()
}