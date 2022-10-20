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


// var viewportIds = []
// const viewportId = (n) => `GRASP_VIEW_${n}`;

const resizeObserver = new ResizeObserver(() => {
    console.log('Size changed');
  
    renderingEngine = window.cornerstone.getRenderingEngine('gravisRenderEngine');
  
    if (renderingEngine) {
      renderingEngine.resize(true, false);
    }
  });
  

class GraspViewer {
    constructor( el ) {
        return (async () => {
            await this.initialize(el);
            return this;
          })();   
         }
    
    createViewportGrid(n) {
        const viewportGrid = document.createElement('div');
        viewportGrid.style.display = 'flex';
        viewportGrid.style.flexDirection = 'row';
        viewportGrid.style.flexWrap = 'wrap';
        var elements = [];
        let size = "500px"
        for (var i=0; i<n; i++) {
            var el = document.createElement('div');
            el.style.width = size;
            el.style.height = size;
            el.style.flex = "0 0 50%";
            viewportGrid.appendChild(el);
            elements.push(el)
            resizeObserver.observe(el);
    
            el.addEventListener(cornerstone.Enums.Events.CAMERA_MODIFIED, (evt) => {
                console.log(evt.detail.camera.position)
            //    console.log({position: evt.detail.camera.position, focalPoint:evt.detail.camera.focalPoint, viewPlaneNormal: evt.detail.camera.viewPlaneNormal} );
            });
        }
        return [viewportGrid, elements];
    }
    
    async initialize( wrapper ) {
        const { RenderingEngine, Types, Enums, volumeLoader, CONSTANTS, setVolumesForViewports} = window.cornerstone; 
        const { ViewportType } = Enums;
        const { ORIENTATION } = CONSTANTS;
        
        const element = document.createElement('div');
        element.id = 'cornerstone-element';
        const [viewportGrid, viewportElements] = this.createViewportGrid(4)

        // console.log(wrapper, viewportGrid, viewportElements);
        wrapper.appendChild(element);
        element.appendChild(viewportGrid);
    
        await cornerstone.helpers.initDemo(); 
    
        // Instantiate a rendering engine
        const renderingEngineId = 'gravisRenderEngine';
        this.renderingEngine = new RenderingEngine(renderingEngineId);    
        // Create a stack viewport
        const viewportInput = [
            {
              viewportId: "VIEW_AX",
              type: ViewportType.ORTHOGRAPHIC,
              element: viewportElements[0],
              defaultOptions: {
    
                orientation: ORIENTATION.AXIAL,
                            // { sliceNormal: [0, 0, 1],
                            // viewUp: [0, -1, 0], }
    
                background: [0, 0, 0],
              },
            },
            {
              viewportId: "VIEW_SAG",
              type: ViewportType.ORTHOGRAPHIC,
              element: viewportElements[1],
              defaultOptions: {
                orientation: ORIENTATION.SAGITTAL,
                            //     sliceNormal:[1, 0, 0],
                            //      viewUp: [0, 0, 1],
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
                viewportId: "VIEW_CINE",
                type: ViewportType.STACK,
                element: viewportElements[3],
                defaultOptions: {
                //   orientation: ORIENTATION.SAGITTAL,
                  background: [0, 0, 0],
                },
              },  
          ];
        this.viewportIds = []
        for (var v of viewportInput) {
            this.viewportIds.push(v.viewportId);
        }
        this.renderingEngine.setViewports(viewportInput)

        this.viewports = []
        for (var id of this.viewportIds) {
            this.viewports.push(this.renderingEngine.getViewport(id))
        }

        // renderingEngine.enableElement(viewportInput);
        cornerstone.tools.synchronizers.createCameraPositionSynchronizer("SYNC_CAMERAS");
    
        this.createTools()
        this.renderingEngine.renderViewports(this.viewportIds);
    }


    createTools() {
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
    
        for (var viewport of this.viewportIds) {
            toolGroupA.addViewport(viewport, "gravisRenderEngine");
        }
    
        const toolGroupB = ToolGroupManager.createToolGroup(toolGroupIdB);
        // toolGroupB.addViewport("VIEW_MIP", "gravisRenderEngine");
        // Add tools to the tool group
        // toolGroup.addTool(WindowLevelTool.toolName );
        // toolGroup.addTool(PanTool.toolName );
    
        toolGroupA.addTool(EllipticalROITool.toolName,
            {
                centerPointRadius: 1,
            });
        
        var styles = cornerstone.tools.annotation.config.style.getDefaultToolStyles()
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
    async setVolumeByImageIds(imageIds, volumeName, keepCamera=true) {
        // const volumeName = series_uid; // Id of the volume less loader prefix
        const volumeLoaderScheme = 'cornerstoneStreamingImageVolume'; // Loader id which defines which volume loader to use
        const volumeId = `${volumeLoaderScheme}:${volumeName}`; // VolumeId with loader id + volume id
        // const viewport = (
        //     renderingEngine.getViewport('GRASP_VIEW')
        // );

        
        let cams = []
        for (var viewport of this.viewports.slice(0,3) ) {
            // viewport = this.renderingEngine.getViewport(v)
            cams.push({viewport, cam:viewport.getCamera(), thickness:viewport.getSlabThickness()})
        }
        // let cams = viewport.getCamera()
        this.volume = await cornerstone.volumeLoader.createAndCacheVolume(volumeId, {
            imageIds,
        });

        // TODO: this is meant to "snap" the direction onto the nearest axes
        // It seems to work but does it always?
        this.volume.imageData.setDirection(this.volume.direction.map(Math.round))
        this.volume.load();
        
        await cornerstone.setVolumesForViewports( 
            this.renderingEngine,
            [{volumeId},],
            this.viewportIds.slice(0,3)
        );

        if ( keepCamera ) {
            for (var c of cams) {
                if (!c.cam.focalPoint.every((k) => k==0)) { // focalPoint is [0,0,0] before any volumes are loaded
                    c.viewport.setCamera( c.cam )
                }
            }
        }
        // setVolumesForViewports(renderingEngine, [{ volumeId }], [viewportId]);
        // viewport.render();
        if (!this.toolAlreadyActive) {
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

            this.toolAlreadyActive = true;

            // const synchronizer =
            // cornerstone.tools.SynchronizerManager.getSynchronizer("SYNC_CAMERAS");
            // synchronizer.add({ renderingEngineId: "gravisRenderEngine", viewportId:"VIEW_SAG" });
            // synchronizer.add({ renderingEngineId: "gravisRenderEngine", viewportId:"VIEW_MIP" });

        }
        this.renderingEngine.renderViewports(this.viewportIds)
    }
    // async setVolumeBySeries(study_uid, series_uid, keepCamera=true) {
    //     // Get Cornerstone imageIds and fetch metadata into RAM
    //     var { imageIds, metadata } = await cacheMetadata(
    //         { studyInstanceUID: study_uid,
    //         seriesInstanceUID: series_uid },
    //         '/wado',
    //     );
    //     await this.setVolumeByImageIds(imageIds, series_uid, keepCamera);
    // }

    async setVolumeByStudy(study_uid, case_id, keepCamera=true) {
        console.log("Caching metadata")
        var { imageIds, metadata } = await cacheMetadata(
            { studyInstanceUID: study_uid },
            '/wado/'+case_id,
        );
        console.log("Cached metadata")
        var seriesByTime = {}
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
        var volumesList = Object.entries(seriesByTime).map((k)=>{return {time:parseFloat(k[0]), seriesList:k[1]}})
        volumesList.sort((k,v)=>(k.time-v.time))
    
        var studyImageIds = []
        for ( var v of volumesList ) {
            imageIds = []
            for (var s of v.seriesList) {
                imageIds.push(getImageId(s,'/wado/'+case_id))
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
    
        await this.setVolumeByImageIds(studyImageIds[0].imageIds, studyImageIds[0].series_uid, keepCamera);
        return studyImageIds
    }
    async setGraspVolume(seriesInfo) {
        await this.setVolumeByImageIds(seriesInfo.imageIds,seriesInfo.series_uid)
    }

    async renderCineFromViewport(n, case_id) {
        var viewport = this.viewports[n];
        var cam = viewport.getCamera()
    
        const volumeId = viewport.getActors()[0].uid;
        var volume = cornerstone.cache.getVolume(volumeId)
        var index = cornerstone.utilities.transformWorldToIndex(volume.imageData, cam.focalPoint)
        
        // console.log(volume)
        // console.log(volume.metadata.SeriesInstanceUID)
        // console.log(viewport)
        // console.log(cam)
        // console.log(volumeId)
        // console.log(index, cam.viewPlaneNormal)
        // job_id = {id: 1}
        var job_id = await startJob("cine", case_id, {"index":index, normal: cam.viewPlaneNormal, viewUp: cam.viewUp})
        // console.log(job_id)
        return job_id
        // const response = await fetch()
    }
    
}

// var toolAlreadyActive = false;


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



// async function setGraspFrame(event) {
//     var series = window.current_study[event.target.value]
//     await setVolumeByImageIds(series.imageIds,series.series_uid, true);
// }

function getCookie(name) {
    let cookieValue = null;

    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();

            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));

                break;
            }
        }
    }

    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

async function startJob(type, case_, params) {
    var body = {
        case: case_,
        parameters: params,
    };
    var result = (await fetch(`/job/${type}`, {
        method: 'POST', 
        credentials: 'same-origin',        
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify(body),
    })).json()
    return result
}

async function getJob(job, info) {
    var result = await (await fetch(`/job/${job}?${new URLSearchParams(info)}`, {
        method: 'GET',   credentials: 'same-origin'
    })).json()
    return result
}
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function getJobInstances(job, info, case_id) {
    console.log("getJobInstances", job, info, case_id);
    for (let i=0;i<100;i++) {
        result = await getJob(job,info)
        if ( result["status"] == "SUCCESS" ) {
            break
        }
        await sleep(1000);
    }
    var urls = []
    for ( var instance of result["dicom_sets"][0] ) {
        urls.push("wadouri:" + 
        "/wado/" +case_id+
        '/studies/' +
        instance.study_uid +
        '/series/' +
        instance.series_uid +
        '/instances/' +
        instance.instance_uid +
        '/frames/1')
    };
    const renderingEngine = window.cornerstone.getRenderingEngine(
        'gravisRenderEngine'
    );
    var viewport = renderingEngine.getViewport("VIEW_CINE");
    await viewport.setStack(urls);
    return urls;
}

window.onload = async function() {
}


