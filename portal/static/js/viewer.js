// import * as cornerstone_test from './static/cornerstone/bundle.js';
// import { Cornerstone } from './static/cornerstone/bundle.js';
// import * as cornerstone from '../../../../cornerstone3D-beta/packages/core'

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
  
function debounce(delay, callback) {
    let timeout
    return (...args) => {
        clearTimeout(timeout)
        timeout = setTimeout(() => {
            callback(...args)
        }, delay)
    }
}
class GraspViewer {
    constructor( ...inp ) {
        return (async () => {
            await this.initialize(...inp);
            return this;
          })();   
         }
    
    createViewportGrid(n=4) {
        const viewportGrid = document.createElement('div');
        viewportGrid.style="display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; height:100%";
        // viewportGrid.style.display = 'flex';
        // viewportGrid.style.flexDirection = 'row';
        // viewportGrid.style.flexWrap = 'wrap';
        var elements = [];
        let size = "50%"
        for (var i=0; i<n; i++) {
            var el = document.createElement('div');
            // el.style.width = size;
            // el.style.height = size;
            // el.style.flex = "0 0 50%";
            viewportGrid.appendChild(el);
            elements.push(el)
            resizeObserver.observe(el);
        }
        return [viewportGrid, elements];
    }
    createViewports( prefix, list, parent, background = [0,0,0] ) {
        const [viewportGrid, viewportElements] = this.createViewportGrid(4)
        parent.appendChild(viewportGrid);
        // element.classList.add("grid-fill")
        // parent.appendChild(element);    
        var viewportInput = list.map(([viewportId, orientation],n) => {
            return {
                viewportId: prefix + "_" + viewportId,
                type: orientation ? cornerstone.Enums.ViewportType.ORTHOGRAPHIC : cornerstone.Enums.ViewportType.STACK,
                element: viewportElements[n],
                defaultOptions: {
                    orientation,
                    background
                },
            }});
        return [ viewportInput, viewportInput.map((c)=>c.viewportId) ]
    }
    async initialize( main, preview ) {
        const { RenderingEngine, Types, Enums, volumeLoader, CONSTANTS, setVolumesForViewports} = window.cornerstone; 
        const { ViewportType } = Enums;

        await cornerstone.helpers.initDemo(); 
        // Instantiate a rendering engine
        const renderingEngineId = 'gravisRenderEngine';
        this.renderingEngine = new RenderingEngine(renderingEngineId);    

        const { ORIENTATION } = cornerstone.CONSTANTS;

        const preview_info = [["AX"],["SAG"],["COR"]]
        const [ previewViewports, previewViewportIds ] = this.createViewports("PREVIEW",preview_info, preview, [0.5,.5,.5])
        const view_info = [["AX",ORIENTATION.AXIAL],["SAG",ORIENTATION.SAGITTAL],["COR",ORIENTATION.CORONAL],["CINE"]]
        const [ viewViewports, viewportIds ] = this.createViewports("VIEW", view_info, main)

        console.log(previewViewports, viewViewports);

        this.renderingEngine.setViewports([...previewViewports, ...viewViewports])

        this.viewportIds = viewportIds
        this.previewViewportIds = previewViewportIds

        this.viewports = viewportIds.map((c)=>this.renderingEngine.getViewport(c))
        this.previewViewports = previewViewportIds.map((c)=>this.renderingEngine.getViewport(c))
        // renderingEngine.enableElement(viewportInput);
        cornerstone.tools.synchronizers.createVOISynchronizer("SYNC_CAMERAS");
    
        this.createTools()
        this.renderingEngine.renderViewports([...this.viewportIds, ...this.previewViewports]);
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
        const tools = [CrosshairsTool, EllipticalROITool, StackScrollMouseWheelTool, VolumeRotateMouseWheelTool, WindowLevelTool, PanTool]
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
        
        toolGroupA.addTool(WindowLevelTool.toolName );
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
        let cams = []

        for (var viewport of this.viewports.slice(0,3) ) {
            cams.push({viewport, cam:viewport.getCamera(), thickness:viewport.getSlabThickness()})
        }
        let voi = null
        try {
            voi = this.viewports[0].getDefaultActor().actor.getProperty().getRGBTransferFunction(0).getRange()
        } catch {}
        // dest_viewport.setVOI({lower, upper})

        console.log("Caching volume...")
        this.volume = await cornerstone.volumeLoader.createAndCacheVolume(volumeId, {
            imageIds,
        });

        // TODO: this is meant to "snap" the direction onto the nearest axes
        // It seems to work but does it always?
        this.volume.imageData.setDirection(this.volume.direction.map(Math.round))

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
            if (voi) {
                this.viewports[0].setProperties( { voiRange: {lower:voi[0], upper:voi[1]}})
            }
        }
        // setVolumesForViewports(renderingEngine, [{ volumeId }], [viewportId]);
        // viewport.render();
        if (!this.toolAlreadyActive) {
            const toolGroup = window.cornerstone.tools.ToolGroupManager.getToolGroup(`STACK_TOOL_GROUP_ID_A`);
            // toolGroup.setToolActive(window.cornerstone.tools.CrosshairsTool.toolName, {
            //     bindings: [{ mouseButton: window.cornerstone.tools.Enums.MouseBindings.Primary }],
            // });
            toolGroup.setToolActive(window.cornerstone.tools.WindowLevelTool.toolName, {
                bindings: [{ mouseButton: window.cornerstone.tools.Enums.MouseBindings.Primary }],
            });
            // toolGroup.setToolActive(cornerstone.tools.EllipticalROITool.toolName, {
            //     bindings: [
            //     {
            //         mouseButton: cornerstone.tools.Enums.MouseBindings.Primary, // Left Click
            //     },
            //     ],
            // });
            toolGroup.setToolActive(window.cornerstone.tools.StackScrollMouseWheelTool.toolName);

            const toolGroupB = window.cornerstone.tools.ToolGroupManager.getToolGroup(`STACK_TOOL_GROUP_ID_B`);
            toolGroupB.setToolActive(window.cornerstone.tools.StackScrollMouseWheelTool.toolName);

            this.toolAlreadyActive = true;

            const synchronizer = cornerstone.tools.SynchronizerManager.getSynchronizer("SYNC_CAMERAS");
            [...this.viewportIds].map(id => synchronizer.add({ renderingEngineId: "gravisRenderEngine", viewportId:id }))
            // synchronizer.add({ renderingEngineId: "gravisRenderEngine", viewportId:"VIEW_MIP" });

        }
        // console.log("Volume starts loading");
        // const loading_finished = new Promise((resolve) => {
        //     this.volume.load( (e) => { console.log("Volume finished loading",e); resolve() });
        // });

        // await this.volume.load();
        this.renderingEngine.renderViewports(this.viewportIds);
        // return loading_finished
    }

    async setVolumeBySeries(study_uid, series_uid, case_id) {
        console.log("Set volume by series", study_uid, series_uid)
        var { imageIds, metadata } = await cacheMetadata(
            { studyInstanceUID: study_uid,
                seriesInstanceUID: series_uid  },
            '/wado/'+case_id,
        );
        await this.setVolumeByImageIds(imageIds, series_uid, true);
    }
    async setPreview(idx, l) {
        try {
            idx = parseInt(idx)
            let [lower, upper] = this.viewports[0].getDefaultActor().actor.getProperty().getRGBTransferFunction(0).getRange()

            for (var v of this.previewViewports) {
                // let voi = {lower: 0, upper: 1229+idx}
                //             let k = v.getDefaultActor().actor.getMapper().getInputData().getPointData().getScalars().getRange()
                v.setVOI({lower, upper})
                await v.setImageIdIndex(Math.floor(idx * v.getImageIds().length / l))
                // v.setVOI({lower:0, upper:1229+(3497-1229)*(idx/v.getImageIds().length)})
                // console.log("Stack VOI range.", v.voiRange.lower, v.voiRange.upper);
                // console.log("Viewport VOI range.", lower, upper);
                // v.setVOI({lower:0, upper: v._getImageDataMetadata(v.csImage).imagePixelModule.windowCenter*2})

            }
        } catch (e) {
            console.error(e);
        }
        // console.log("VOI", lower,upper)
        
    }

    async updatePreview(case_id, n=null, idx=0) {
        console.log("Updating previews...")
        let update = [n]
        if (n==null){
            update = [0, 1, 2]
        }
        await Promise.all(update.map(async (n)=> {
            console.log(`Preview ${n}`)
            let [lower, upper] = this.viewports[0].getDefaultActor().actor.getProperty().getRGBTransferFunction(0).getRange()
            this.previewViewports[n].setVOI({lower, upper})
            await this.renderCineFromViewport(n,case_id, this.previewViewports[n]) 
            this.previewViewports[n].setVOI({lower, upper})
            // await this.previewViewports[n].setImageIdIndex(idx)
            // this.previewViewports[n].setVOI()
        }))
    }
    async switchSeries(study_uid, series_uid, case_id) {
        await this.setVolumeBySeries(study_uid, series_uid, case_id);
        await new Promise((resolve) => {
            this.volume.load( (e) => { console.log("Volume finished loading",e); resolve() });
        });
    }
    async switchStudy(study_uid, case_id, keepCamera=true) {
        var graspVolumeInfo = await (await fetch(`/api/grasp/data/${case_id}/${study_uid}`, {
            method: 'GET',   credentials: 'same-origin'
        })).json()
        document.getElementById("volume-picker").setAttribute("min",0)
        document.getElementById("volume-picker").setAttribute("max",graspVolumeInfo.length-1)
        document.getElementById("volume-picker").setAttribute("value",0)

        
        
        this.viewports.map((v, n)=> {
            v.element.addEventListener("wheel", debounce(250, async (evt) => {
                // console.log(v.getCamera().position)
                try {
                    await this.updatePreview(case_id, n)
                } catch (e) {
                    console.error(e);
                }
            //    console.log({position: evt.detail.camera.position, focalPoint:evt.detail.camera.focalPoint, viewPlaneNormal: evt.detail.camera.viewPlaneNormal} );
            }));
            v.element.addEventListener("CORNERSTONE_PRE_STACK_NEW_IMAGE", (evt) => {console.log(evt)})
        });

        await this.setVolumeBySeries(study_uid, graspVolumeInfo[0]["series_uid"], case_id),
        this.volume.load(()=>{ console.log("Volume loaded")})
        try {
            await this.updatePreview(case_id)
        } catch (e) {
            console.error(e);
        }

        console.log("Study switched");
        return graspVolumeInfo
    }
    // async setGraspVolume(seriesInfo) {
    //     await this.setVolumeByImageIds(seriesInfo.imageIds,seriesInfo.series_uid)
    // }

    async renderCineFromViewport(n, case_id, dest_viewport=null) {
        var viewport = this.viewports[n];
        var cam = viewport.getCamera()
    
        const volumeId = viewport.getActors()[0].uid;
        var volume = cornerstone.cache.getVolume(volumeId)
        var index = cornerstone.utilities.transformWorldToIndex(volume.imageData, cam.focalPoint)

        if (cam.viewPlaneNormal[0] == 1) {
            var view = "sag"
            var val = index[2]
        } else if  (cam.viewPlaneNormal[1] == 1) {
            var view = "cor"
            var val = index[0]
        } else {
            var view = "ax"
            var val = index[1]
        }
        var info = await (await fetch(`/api/grasp/preview/${case_id}/${view}/${val}`, {
            method: 'GET',   credentials: 'same-origin'
        })).json() 
        console.log("Preview info:", info)
        var urls = info
        // for ( var instance of info ) {
        //     urls.push("wadouri:" + 
        //     "/wado/" +case_id+
        //     '/studies/' +
        //     instance.study_uid +
        //     '/series/' +
        //     instance.series_uid +
        //     '/instances/' +
        //     instance.instance_uid +
        //     '/frames/1')
        // };

        
        // var result = await doJob("cine", case_id, {"index":index, normal: cam.viewPlaneNormal, viewUp: cam.viewUp})
        // var urls = getJobInstances(result, case_id)

        dest_viewport = dest_viewport? dest_viewport : this.viewports[3]
        // dest_viewport.setProperties( { voiRange: viewport.getProperties().voiRange });
        let [lower, upper] = viewport.getDefaultActor().actor.getProperty().getRGBTransferFunction(0).getRange()
        dest_viewport.setVOI({lower, upper})
        await dest_viewport.setStack(urls,dest_viewport.currentImageIdIndex);
        // console.log(cornerstone.requestPoolManager.getRequestPool().interaction)

        // cornerstone.tools.utilities.stackPrefetch.enable(dest_viewport.element);
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

async function doJob(type, case_, params) {
    const id = await startJob(type, case_, params);
    console.log(`Do Job`,id);
    for (let i=0;i<100;i++) {
        result = await getJob(type,id)
        if ( result["status"] == "SUCCESS" ) {
            break
        }
        await sleep(100);
    }
    return result;
}

async function startJob(type, case_, params) {
    var body = {
        case: case_,
        parameters: params,
    };
    var result = await (await fetch(`/job/${type}`, {
        method: 'POST', 
        credentials: 'same-origin',        
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify(body),
    })).json()
    return result.id
}

async function getJob(job, id) {
    var result = await (await fetch(`/job/${job}?id=${id}`, { //${new URLSearchParams({id})
        method: 'GET',   credentials: 'same-origin'
    })).json()
    return result
}
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function getJobInstances(result, case_id) {
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
    return urls;
}

window.onload = async function() {
}


