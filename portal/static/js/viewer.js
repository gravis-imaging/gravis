// import * as cornerstone_test from './static/cornerstone/bundle.js';
// import { Cornerstone } from './static/cornerstone/bundle.js';
// console.log(Cornerstone)
const SOP_INSTANCE_UID = '00080018';
const STUDY_TIME = '00080030'
const SERIES_TIME = '00080031'
const SERIES_INSTANCE_UID = '0020000E'; 
const STUDY_INSTANCE_UID = '0020000D';


function getImageId(instanceMetaData, wadoRsRoot) {
    const StudyInstanceUID = instanceMetaData[STUDY_INSTANCE_UID].Value[0];
    const SeriesInstanceUID = instanceMetaData[SERIES_INSTANCE_UID].Value[0];
    const SOPInstanceUID = instanceMetaData[SOP_INSTANCE_UID].Value[0];

    const prefix = 'wadouri:'

    return prefix +
      wadoRsRoot +
      '/studies/' +
      StudyInstanceUID +
      '/series/' +
      SeriesInstanceUID +
      '/instances/' +
      SOPInstanceUID +
      '/frames/1';
}

async function cacheMetadata(
    studySearchOptions,
    wadoRsRoot,
  ){
    
    const client = new dicomweb.DICOMwebClient({ url: wadoRsRoot });
    var metadata;
    if (studySearchOptions.seriesInstanceUID ) {
        metadata = await client.retrieveSeriesMetadata(studySearchOptions);
    } else {
        metadata = await client.retrieveStudyMetadata(studySearchOptions);
    }
    imageIds = []
    for (var instanceMetaData of metadata) {
        imageId = getImageId(instanceMetaData, wadoRsRoot);
        cornerstone.cornerstoneWADOImageLoader.wadors.metaDataManager.add(
          imageId,
          instanceMetaData
        );
        imageIds.push(imageId);
    }
    return { imageIds, metadata };
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
            // orientation: ORIENTATION.SAGITTAL,
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
    viewport.render();
}

async function setVolumeByImageIds(imageIds, volumeName, keepCamera=true) {
    // const volumeName = series_uid; // Id of the volume less loader prefix
    const volumeLoaderScheme = 'cornerstoneStreamingImageVolume'; // Loader id which defines which volume loader to use
    const volumeId = `${volumeLoaderScheme}:${volumeName}`; // VolumeId with loader id + volume id
    const renderingEngine = window.cornerstone.getRenderingEngine(
        'gravisRenderEngine'
    );
    const viewport = (
        renderingEngine.getViewport('GRASP_VIEW')
    );

    let cam = viewport.getCamera()
    const volume = await cornerstone.volumeLoader.createAndCacheVolume(volumeId, {
        imageIds,
    });
    volume.load();
    
    await viewport.setVolumes([
        { volumeId },
        
    ]);
    if ( keepCamera ) {
        if (!cam.focalPoint.every((k) => k==0)) { // focalPoint is [0,0,0] before any volumes are loaded
            viewport.setCamera( cam )
        }
    }
// setVolumesForViewports(renderingEngine, [{ volumeId }], [viewportId]);
    viewport.render();
}

async function setVolumeBySeries(study_uid, series_uid, keepCamera=true) {

    // Get Cornerstone imageIds and fetch metadata into RAM
    var { imageIds, metadata } = await cacheMetadata(
        { studyInstanceUID: study_uid,
        seriesInstanceUID: series_uid },
        '/wado',
    );
    await setVolumeByImageIds(imageIds, series_uid, keepCamera);
}

async function setVolumeByStudy(study_uid, series_uid, keepCamera=true) {
    var { imageIds, metadata } = await cacheMetadata(
        { studyInstanceUID: study_uid },
        '/wado',
    );
    seriesByTime = {}
    for (var k of metadata){
        var time = parseFloat(k[SERIES_TIME].Value[0]) - parseFloat(k[STUDY_TIME].Value[0])
        if (seriesByTime[time] == undefined ){
            seriesByTime[time] = []
        }
        seriesByTime[time].push(k)
    }
    volumesList = Object.entries(seriesByTime).map((k)=>[parseFloat(k[0]),k[1]])
    volumesList.sort((k,v)=>(k[0]-v[0]))
    
    studyImageIds = []
    for ( var v of volumesList ) {
        imageIds = []
        for (var k of v[1]) {
            imageIds.push(getImageId(k,'/wado'))
        }
        var series_uid = v[1][0][SERIES_INSTANCE_UID].Value[0]
        studyImageIds.push([imageIds, series_uid])
    }
    console.log(studyImageIds)
    window.current_study = studyImageIds
    document.getElementById("volume-picker").setAttribute("min",0)
    document.getElementById("volume-picker").setAttribute("max",window.current_study.length-1)
    document.getElementById("volume-picker").setAttribute("value",0)

    await setVolumeByImageIds(studyImageIds[0][0], series_uid, keepCamera);
    // console.log(metadata)
}

async function setGraspFrame(event) {
    var study = window.current_study[event.target.value]
    await setVolumeByImageIds(study[0],study[1], true);
}

window.onload = async function() {
    await run()
}