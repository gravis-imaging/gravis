// import * as cornerstone_test from './static/cornerstone/bundle.js';
// import { Cornerstone } from './static/cornerstone/bundle.js';
// console.log(Cornerstone)
const SOP_INSTANCE_UID = '00080018';
const STUDY_DATE = '00080020';
const STUDY_TIME = '00080030';
const SERIES_DATE = '00080021';
const SERIES_TIME = '00080031';
const SERIES_INSTANCE_UID = '0020000E'; 
const STUDY_INSTANCE_UID = '0020000D';
const SERIES_DESCRIPTION = '0008103E';

function getMeta(data, val) {
    return data[val].Value[0]
}

function getImageId(instanceMetaData, wadoRsRoot) {
    const StudyInstanceUID = getMeta(instanceMetaData,STUDY_INSTANCE_UID)
    const SeriesInstanceUID = getMeta(instanceMetaData,SERIES_INSTANCE_UID)
    const SOPInstanceUID = getMeta(instanceMetaData,SOP_INSTANCE_UID)

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
        VolumeRotateMouseWheelTool,
        ZoomTool,
        ToolGroupManager,
        CrosshairsTool,
        EllipticalROITool,
        Enums: csToolsEnums,
    } = cornerstoneTools;
    const { MouseBindings } = csToolsEnums;

    const toolGroupIdA = `STACK_TOOL_GROUP_ID_A`;
    const toolGroupIdB = `STACK_TOOL_GROUP_ID_B`;

    // Add tools to Cornerstone3D
    // cornerstoneTools.addTool(PanTool);
    // cornerstoneTools.addTool(WindowLevelTool);
    const tools = [CrosshairsTool, EllipticalROITool, StackScrollMouseWheelTool, VolumeRotateMouseWheelTool]
    tools.map(cornerstoneTools.addTool)

    // Define a tool group, which defines how mouse events map to tool commands for
    // Any viewport using the group
    const toolGroupA = ToolGroupManager.createToolGroup(toolGroupIdA);

    for (var viewport of viewportIds.slice(0,3)) {
        toolGroupA.addViewport(viewport, "gravisRenderEngine");
    }

    const toolGroupB = ToolGroupManager.createToolGroup(toolGroupIdB);
    toolGroupB.addViewport("VIEW_MIP", "gravisRenderEngine");
    // Add tools to the tool group
    // toolGroup.addTool(WindowLevelTool.toolName );
    // toolGroup.addTool(PanTool.toolName );

    toolGroupA.addTool(EllipticalROITool.toolName,
        {
            centerPointRadius: 1,
        });
    
    styles = cornerstone.tools.annotation.config.style.getDefaultToolStyles()
    styles.global.color = "rgb(255,0,0)"
    styles.global.lineWidth = "5"
    cornerstone.tools.annotation.config.style.setDefaultToolStyles(styles)
    toolGroupA.addTool(StackScrollMouseWheelTool.toolName );


    toolGroupB.addTool(StackScrollMouseWheelTool.toolName );
    // toolGroupA.addTool(CrosshairsTool.toolName, {
    //     getReferenceLineColor: (id) => { return ({"VIEW_AX": "rgb(255, 0, 0)","VIEW_SAG": "rgb(255, 255, 0)","VIEW_COR": "rgb(0, 255, 0)",})[id]},
    //     // getReferenceLineControllable: (id)=> true,
    //     // getReferenceLineDraggableRotatable: (id)=> true,
    //     // getReferenceLineSlabThicknessControlsOn: (id)=> false,
    //     // filterActorUIDsToSetSlabThickness: [viewportId(4)]
    //   });
    
    // toolGroup.addTool(WindowLevelTool.toolName, { volumeId } );
    // toolGroup.addTool(PanTool.toolName,  { volumeId } );
    // toolGroup.addTool(ZoomTool.toolName,  { volumeId } );
    toolGroupB.addTool(StackScrollMouseWheelTool.toolName);


    // Set the initial state of the tools, here all tools are active and bound to
    // Different mouse inputs
    // toolGroup.setToolActive(WindowLevelTool.toolName, {
    // bindings: [
    //     {
    //     mouseButton: MouseBindings.Primary, // Left Click
    //     },
    // ],
    // });

    // toolGroup.setToolActive(CrosshairsTool.toolName, {
    //     bindings: [{ mouseButton: MouseBindings.Primary }],
    // });
    
    // toolGroup.setToolActive(PanTool.toolName, {
    // bindings: [
    //     {
    //     mouseButton: MouseBindings.Auxiliary, // Middle Click
    //     },
    // ],
    // });
    // toolGroup.setToolActive(ZoomTool.toolName, {
    // bindings: [
    //     {
    //     mouseButton: MouseBindings.Secondary, // Right Click
    //     },
    // ],
    // });
    // As the Stack Scroll mouse wheel is a tool using the `mouseWheelCallback`
    // hook instead of mouse buttons, it does not need to assign any mouse button.
    return toolGroupA;
}
var viewportIds = []
// const viewportId = (n) => `GRASP_VIEW_${n}`;

const resizeObserver = new ResizeObserver(() => {
    console.log('Size changed');
  
    renderingEngine = window.cornerstone.getRenderingEngine('gravisRenderEngine');
  
    if (renderingEngine) {
      renderingEngine.resize(true, false);
    }
  });
  
function createViewportGrid(n) {
    const viewportGrid = document.createElement('div');
    viewportGrid.style.display = 'flex';
    // viewportGrid.style.gridTemplateColumns = '1fr 1fr';

    viewportGrid.style.flexDirection = 'row';
    viewportGrid.style.flexWrap = 'wrap';
    // viewportGrid.style.width = '1000px';
    var elements = [];
    size = "500px"
    for (var i=0; i<n; i++) {
        var el = document.createElement('div');
        el.style.width = size;
        el.style.height = size;
        el.style.flex = "0 0 50%";
        viewportGrid.appendChild(el);
        elements.push(el)
        resizeObserver.observe(el);

        el.addEventListener(cornerstone.Enums.Events.CAMERA_MODIFIED, (evt) => {
            console.log({position: evt.detail.camera.position, focalPoint:evt.detail.camera.focalPoint} );
        });
    }
    return [viewportGrid, elements];
}



async function initializeGraspViewer(wrapper) {
    const { RenderingEngine, Types, Enums, volumeLoader, CONSTANTS, setVolumesForViewports} = window.cornerstone;

    
    const { ViewportType } = Enums;
    const { ORIENTATION } = CONSTANTS;


    const element = document.createElement('div');
    element.id = 'cornerstone-element';
    // element.style.width = '100%';
    // element.style.height = '100%';

    const [viewportGrid, viewportElements] = createViewportGrid(4)
    console.log(wrapper, viewportGrid, viewportElements);
    wrapper.appendChild(element);
    element.appendChild(viewportGrid);

    await cornerstone.helpers.initDemo(); 

    // Instantiate a rendering engine
    const renderingEngineId = 'gravisRenderEngine';
    const renderingEngine = new RenderingEngine(renderingEngineId);

    // Create a stack viewport
    const viewportInput = [
        {
          viewportId: "VIEW_AX",
          type: ViewportType.ORTHOGRAPHIC,
          element: viewportElements[0],
          defaultOptions: {
            orientation: ORIENTATION.AXIAL,
            background: [0, 0, 0],
          },
        },
        {
          viewportId: "VIEW_SAG",
          type: ViewportType.ORTHOGRAPHIC,
          element: viewportElements[1],
          defaultOptions: {
            orientation: ORIENTATION.SAGITTAL,
            background: [0, 0, 0],
          },
        },
        {
          viewportId: "VIEW_COR",
          type: ViewportType.ORTHOGRAPHIC,
          element: viewportElements[2],
          defaultOptions: {
            orientation: ORIENTATION.CORONAL,
            background:[0, 0, 0],
          },
        },
        {
            viewportId: "VIEW_MIP",
            type: ViewportType.ORTHOGRAPHIC,
            element: viewportElements[3],
            defaultOptions: {
              orientation: ORIENTATION.SAGITTAL,
              background: [0, 0, 0],
            },
          },  
      ];
    for (v of viewportInput) {
        viewportIds.push(v.viewportId);
    }
    renderingEngine.setViewports(viewportInput)
    // renderingEngine.enableElement(viewportInput);
    cornerstone.tools.synchronizers.createCameraPositionSynchronizer("SYNC_CAMERAS");

    var toolGroup = createTools()
    

    renderingEngine.renderViewports(viewportIds);
}
var toolAlreadyActive = false;

async function setVolumeByImageIds(imageIds, volumeName, keepCamera=true) {
    // const volumeName = series_uid; // Id of the volume less loader prefix
    const volumeLoaderScheme = 'cornerstoneStreamingImageVolume'; // Loader id which defines which volume loader to use
    const volumeId = `${volumeLoaderScheme}:${volumeName}`; // VolumeId with loader id + volume id
    const renderingEngine = window.cornerstone.getRenderingEngine(
        'gravisRenderEngine'
    );
    // const viewport = (
    //     renderingEngine.getViewport('GRASP_VIEW')
    // );

    
    let cams = []
    for (var v of viewportIds.slice(0,3) ) {
        viewport = renderingEngine.getViewport(v)
        cams.push({viewport, cam:viewport.getCamera(), thickness:viewport.getSlabThickness()})
    }
    // let cams = viewport.getCamera()
    const volume = await cornerstone.volumeLoader.createAndCacheVolume(volumeId, {
        imageIds,
    });
    volume.load();
    
    await cornerstone.setVolumesForViewports( 
        renderingEngine,
        [{volumeId},],
        viewportIds.slice(0,3)
      );

      const slabThickness = Math.sqrt(
        volume.dimensions[0] * volume.dimensions[0] +
        volume.dimensions[1] * volume.dimensions[1] +
        volume.dimensions[2] * volume.dimensions[2]
      );
    await cornerstone.setVolumesForViewports(
        renderingEngine,
        [{volumeId, slabThickness},],
        viewportIds.slice(3)
      );
      
    // await viewport.setVolumes([
    //     { volumeId },
    // ]);
    if ( keepCamera ) {
        // cams[0].viewport.setSlabThickness(cams[0].thickness)

        for (var c of cams) {
            if (!c.cam.focalPoint.every((k) => k==0)) { // focalPoint is [0,0,0] before any volumes are loaded
                // c.viewport.setSlabThickness(c.thickness)
                c.viewport.setCamera( c.cam )
            }
        }
    }
// setVolumesForViewports(renderingEngine, [{ volumeId }], [viewportId]);
    // viewport.render();
    if (!toolAlreadyActive) {
        const toolGroup = window.cornerstone.tools.ToolGroupManager.getToolGroup(`STACK_TOOL_GROUP_ID_A`);
        // toolGroup.setToolActive(window.cornerstone.tools.CrosshairsTool.toolName, {
        //     bindings: [{ mouseButton: window.cornerstone.tools.Enums.MouseBindings.Primary }],
        // });
        toolGroup.setToolActive(cornerstone.tools.EllipticalROITool.toolName, {
            bindings: [
              {
                mouseButton: cornerstone.tools.Enums.MouseBindings.Primary, // Left Click
              },
            ],
          });
        toolGroup.setToolActive(window.cornerstone.tools.StackScrollMouseWheelTool.toolName);

        const toolGroupB = window.cornerstone.tools.ToolGroupManager.getToolGroup(`STACK_TOOL_GROUP_ID_B`);
        toolGroupB.setToolActive(window.cornerstone.tools.StackScrollMouseWheelTool.toolName);

        toolAlreadyActive = true;

        // const synchronizer =
        // cornerstone.tools.SynchronizerManager.getSynchronizer("SYNC_CAMERAS");
        // synchronizer.add({ renderingEngineId: "gravisRenderEngine", viewportId:"VIEW_SAG" });
        // synchronizer.add({ renderingEngineId: "gravisRenderEngine", viewportId:"VIEW_MIP" });

    }
    renderingEngine.renderViewports(viewportIds)
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
function parseDicomTime(date, timestamp) {    
    const p = {
        year: parseInt(date.slice(0,4)),
        month: parseInt(date.slice(4,6))-1, // Javascript months are 0-indexed, DICOM months are 1-indexed
        day: parseInt(date.slice(6,8)),
        hour: parseInt(timestamp.slice(0,2)),
        minute: parseInt(timestamp.slice(2,4)),
        second: parseInt(timestamp.slice(4,6)),
        millisecond: 0
      };
    if (timestamp.length > 6) {
        p.millisecond = Math.round(1000*parseFloat(timestamp.slice(6)))
    }
    return new Date(p.year,p.month,p.day,p.hour,p.minute,p.second,p.millisecond)
}

async function setVolumeByStudy(study_uid, keepCamera=true) {
    var { imageIds, metadata } = await cacheMetadata(
        { studyInstanceUID: study_uid },
        '/wado',
    );
    seriesByTime = {}
    const studyTime = parseDicomTime(getMeta(metadata[0],STUDY_DATE),getMeta(metadata[0],STUDY_TIME))
    console.log("Study time", studyTime)
    for (var k of metadata){
        const seriesTime = parseDicomTime(getMeta(k,SERIES_DATE),getMeta(k,SERIES_TIME))
        const time = seriesTime - studyTime

        if (seriesByTime[time] == undefined ){
            seriesByTime[time] = []
        }
        seriesByTime[time].push(k)
    }
    volumesList = Object.entries(seriesByTime).map((k)=>{return {time:parseFloat(k[0]), seriesList:k[1]}})
    volumesList.sort((k,v)=>(k.time-v.time))

    studyImageIds = []
    for ( var v of volumesList ) {
        imageIds = []
        for (var s of v.seriesList) {
            imageIds.push(getImageId(s,'/wado'))
        }
        var series_uid = getMeta(v.seriesList[0],SERIES_INSTANCE_UID);
        var series_description = getMeta(v.seriesList[0],SERIES_DESCRIPTION);
        var time = v.time/1000.0;
        studyImageIds.push({imageIds, series_uid, series_description, time})
    }
    console.log(studyImageIds)
    document.getElementById("volume-picker").setAttribute("min",0)
    document.getElementById("volume-picker").setAttribute("max",studyImageIds.length-1)
    document.getElementById("volume-picker").setAttribute("value",0)

    await setVolumeByImageIds(studyImageIds[0].imageIds, studyImageIds[0].series_uid, keepCamera);
    return studyImageIds

    // console.log(metadata)
}

async function setGraspVolume(seriesInfo) {
    await setVolumeByImageIds(seriesInfo.imageIds,seriesInfo.series_uid)
}

// async function setGraspFrame(event) {
//     var series = window.current_study[event.target.value]
//     await setVolumeByImageIds(series.imageIds,series.series_uid, true);
// }

window.onload = async function() {
}
