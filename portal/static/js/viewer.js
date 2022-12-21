import { AnnotationManager } from "./annotations.js"
import { doJob } from "./utils.js"

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
// document.addEventListener(
//     "wheel",
//     function touchHandler(e) {
//       if (e.ctrlKey) {
//         e.preventDefault();
//       }
//     }, { passive: false } 
// );
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
    let metadata = await (studySearchOptions.seriesInstanceUID? 
            client.retrieveSeriesMetadata(studySearchOptions) :
            client.retrieveStudyMetadata(studySearchOptions))
    let imageIds = []
    for (var instanceMetaData of metadata) {
        let imageId = getImageId(instanceMetaData, wadoRsRoot);
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
    let renderingEngine = window.cornerstone.getRenderingEngine('gravisRenderEngine');
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
    renderingEngine;
    viewportIds = [];
    previewViewportIds = [];

    viewports = [];
    previewViewports = [];

    chart;
    toolsAlreadyActive = false;

    dicom_set;
    case_id;
    study_uid;
    volume; 
    selected_time = 0;
    chart_options = {};
    constructor( ...inp ) {
        return (async () => {
            await this.initialize(...inp);
            return this;
          })();   
         }
    
    getState() {
        if (!this.viewports[0].getDefaultActor()) {
            return;
        }
        const cameras = this.viewports.map(v=>v.getCamera());
        const voi = this.getVolumeVOI(this.viewports[0]);
        const annotations = this.annotation_manager.getAllAnnotations();
        for (let a of annotations) {
            a.data.cachedStats = {}
        }
        return { cameras, voi, annotations };
    }
    saveState() {
        if (!this.case_id) return;
        console.info("Saving state.")
        const state = this.getState()
        if (state)
            localStorage.setItem(this.case_id, JSON.stringify(state));
    }
    loadState() {
        var state;
        state = JSON.parse(localStorage.getItem(this.case_id));
        if (!state) {
            return;
        }
        console.info("Loading state");
        state.cameras.map((c,n)=> {
            this.viewports[n].setCamera(c);
        })
        if ( state.voi ) {
            const [ lower, upper ] = state.voi;
            this.viewports[0].setProperties( { voiRange: {lower,upper}})
        }
        if ( state.annotations ) {
            const annotationState = cornerstone.tools.annotation.state;
            let old_annotations = []
            for (let v of this.viewports.slice(0,3)) {
                old_annotations = this.annotation_manager.getAllAnnotations(v);
                if (!old_annotations) continue;
                for (let a of old_annotations) {
                    annotationState.removeAnnotation(a.annotationUID, v.element)
                }
            }
            for (var a of Object.keys(this.annotation_manager.annotations)) {
                delete this.annotation_manager.annotations[a];
            }
            for (var a of state.annotations) {
                this.annotation_manager.annotations[a.annotationUID] = { uid: a.annotationUID, label: a.data.label, ...a.metadata }
                annotationState.addAnnotation(this.viewports[0].element,a)
            }
        }
        this.renderingEngine.renderViewports(this.viewportIds);
        console.log(state);
    }

    backgroundSaveState(){ 
        const saveStateSoon = () => {
            requestIdleCallback(this.saveState.bind(this));
        }
        document.addEventListener('visibilitychange', ((event) => { 
            if (document.visibilityState === 'hidden') {
                this.saveState();
            } else if (document.visibilityState === 'visible') {
                this.loadState();
            }
        }).bind(this));
        return setInterval(saveStateSoon.bind(this), 1000);
    }

    async initialize( main, preview ) {
            const { RenderingEngine, Types, Enums, volumeLoader, CONSTANTS, setVolumesForViewports} = window.cornerstone; 
            const { ViewportType } = Enums;
            // Force cornerstone to try to use GPU rendering even if it thinks the GPU is weak.
            cornerstone.setUseCPURendering(false);
            await cornerstone.helpers.initDemo(); 
            // Instantiate a rendering engine
            const renderingEngineId = 'gravisRenderEngine';
            this.renderingEngine = new RenderingEngine(renderingEngineId);    
    
            const { ORIENTATION } = cornerstone.CONSTANTS;
    
            const preview_info = [["AX"],["SAG"],["COR"]]
            const [ previewViewports, previewViewportIds ] = this.createViewports("PREVIEW",preview_info, preview)
            /*
            ["COR",{
                                sliceNormal: [ 0, -1, 0 ],
                                viewUp: [ 0, 0, 1 ]
            }],*/
            const view_info = [["AX",ORIENTATION.AXIAL],["SAG",ORIENTATION.SAGITTAL],["COR",ORIENTATION.CORONAL],["CINE"]]
            const [ viewViewports, viewportIds ] = this.createViewports("VIEW", view_info, main)
            this.renderingEngine.setViewports([...previewViewports, ...viewViewports])
    
            this.viewportIds = viewportIds
            this.previewViewportIds = previewViewportIds
            this.viewports = viewportIds.map((c)=>this.renderingEngine.getViewport(c))
            this.previewViewports = previewViewportIds.map((c)=>this.renderingEngine.getViewport(c))

            this.annotation_manager = new AnnotationManager(this)
            cornerstone.tools.synchronizers.createVOISynchronizer("SYNC_CAMERAS");
            this.createTools();
            this.renderingEngine.renderViewports([...this.viewportIds, ...this.previewViewports]);
            this.chart = this.annotation_manager.initChart();

            this.viewports.slice(0,3).map((v, n)=> {
                v.element.addEventListener("CORNERSTONE_CAMERA_MODIFIED", debounce(250, async (evt) => {
                    if (! v.getDefaultActor() ) return;
                    try {
                        await this.updatePreview(n)
                        this.previewViewports[n].setZoom(v.getZoom());
                        this.previewViewports[n].setPan(v.getPan());
                        this.renderingEngine.renderViewports([this.previewViewportIds[n]])    
                    } catch (e) {
                        console.error(e);
                    }
                }));
                
                v.element.addEventListener("CORNERSTONE_TOOLS_ANNOTATION_RENDERED", debounce(100, (evt) => {
                    this.annotation_manager.updateChart()
                }));
            });
        }
    
    
    createViewportGrid(n=4) {
        const viewportGrid = document.createElement('div');
        viewportGrid.style="display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; height:100%";
        var elements = [];
        let size = "50%"
        for (var i=0; i<n; i++) {
            var el = document.createElement('div');
            viewportGrid.appendChild(el);
            elements.push(el)
            resizeObserver.observe(el);
            el.oncontextmenu = e=>e.preventDefault();
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

    createTools() {
        const cornerstoneTools = window.cornerstone.tools;
        const {
            PanTool,
            ZoomTool,
            WindowLevelTool,
            StackScrollMouseWheelTool,
            VolumeRotateMouseWheelTool,

            ToolGroupManager,
            CrosshairsTool,
            GravisROITool,
            ProbeTool,
            Enums: csToolsEnums,
        } = cornerstoneTools;
        const { MouseBindings } = csToolsEnums;
        const tools = [CrosshairsTool, GravisROITool, StackScrollMouseWheelTool, VolumeRotateMouseWheelTool, WindowLevelTool, PanTool, ZoomTool, ProbeTool]
        tools.map(cornerstoneTools.addTool)
        // Define a tool group, which defines how mouse events map to tool commands for
        // Any viewport using the group
        const toolGroupMain = ToolGroupManager.createToolGroup(`STACK_TOOL_GROUP_MAIN`);
        const toolGroupAux = ToolGroupManager.createToolGroup(`STACK_TOOL_GROUP_AUX`);

        const allGroupTools = [ StackScrollMouseWheelTool.toolName, WindowLevelTool.toolName, PanTool.toolName, ZoomTool.toolName ]
        for (var viewport of this.viewportIds.slice(0,3)) {
            toolGroupMain.addViewport(viewport, "gravisRenderEngine");
        }

        toolGroupAux.addViewport(this.viewportIds[3], "gravisRenderEngine");
        allGroupTools.map( tool => [toolGroupMain, toolGroupAux].map(group => group.addTool(tool)))

        toolGroupMain.addTool(ProbeTool.toolName);
        toolGroupMain.addTool(GravisROITool.toolName,
            {
                centerPointRadius: 1,
            });
        
        var styles = cornerstone.tools.annotation.config.style.getDefaultToolStyles()
        styles.global.lineWidth = "1"
        cornerstone.tools.annotation.config.style.setDefaultToolStyles(styles)
        toolGroupMain.addTool(CrosshairsTool.toolName, {
            getReferenceLineColor: (id) => { return ({"VIEW_AX": "rgb(255, 255, 100)",
                                                      "VIEW_SAG": "rgb(100, 100, 255)",
                                                      "VIEW_COR": "rgb(255, 100, 100)",})[id]},
            getReferenceLineRotatable: (id) => false,
            getReferenceLineSlabThicknessControlsOn: (id) => false,
            // filterActorUIDsToSetSlabThickness: [viewportId(4)]
          });
        return toolGroupMain;
    }
    enableTools() {
        if (this.toolsAlreadyActive) {
            return
        }
        const Tools = window.cornerstone.tools;
        const Enums = Tools.Enums;
        const toolGroupMain = Tools.ToolGroupManager.getToolGroup(`STACK_TOOL_GROUP_MAIN`);
        const toolGroupAux = Tools.ToolGroupManager.getToolGroup(`STACK_TOOL_GROUP_AUX`);


        toolGroupMain.setToolActive(Tools.CrosshairsTool.toolName, {
            bindings: [{ 
                mouseButton: Enums.MouseBindings.Primary,
                modifierKey: Enums.KeyboardBindings.Shift,
            }],
        });
        toolGroupMain.setToolActive(Tools.WindowLevelTool.toolName, {
            bindings: [{ 
                mouseButton: Enums.MouseBindings.Primary,
                modifierKey: Enums.KeyboardBindings.Ctrl,
            }],
        });
        toolGroupMain.setToolActive(Tools.ZoomTool.toolName, {
            bindings: [{ 
                mouseButton: Enums.MouseBindings.Secondary,
                modifierKey: Enums.KeyboardBindings.Alt,
            }],
        });
        toolGroupMain.setToolActive(Tools.PanTool.toolName, {
            bindings: [{ 
                mouseButton: Enums.MouseBindings.Primary,
                modifierKey: Enums.KeyboardBindings.Alt,
            }],
        });

        toolGroupMain.setToolPassive(Tools.GravisROITool.toolName, {
            bindings: [
            {
                mouseButton: Enums.MouseBindings.Primary,
            },
            ],
        });

        toolGroupAux.setToolActive(Tools.WindowLevelTool.toolName, {
            bindings: [{ 
                mouseButton: Enums.MouseBindings.Primary,
            }],
        });
        toolGroupMain.setToolPassive(Tools.ProbeTool.toolName, {
            bindings: [
            {
                mouseButton: Enums.MouseBindings.Primary,
            },
            ],
        });
        [toolGroupMain, toolGroupAux].map(g=>g.setToolActive(Tools.StackScrollMouseWheelTool.toolName))
        const synchronizer = Tools.SynchronizerManager.getSynchronizer("SYNC_CAMERAS");
        [...this.viewportIds.slice(0,3)].map(id => synchronizer.add({ renderingEngineId: "gravisRenderEngine", viewportId:id }))
        this.toolsAlreadyActive = true;
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
            voi = this.getVolumeVOI(this.viewports[0]);
        } catch {}
        // dest_viewport.setVOI({lower, upper})

        console.log("Caching volume...")
        this.volume = await cornerstone.volumeLoader.createAndCacheVolume(volumeId, {
            imageIds,
        });

        // this is meant to "snap" the direction onto the nearest axes
        this.volume.imageData.setDirection(this.volume.direction.map(Math.round))

        await cornerstone.setVolumesForViewports( 
            this.renderingEngine,
            [{volumeId},],
            this.viewportIds.slice(0,3)
        );      

        if ( keepCamera ) {
            for (var c of cams) {
                if (!c.cam.focalPoint.every( k => k==0)) { // focalPoint is [0,0,0] before any volumes are loaded
                    c.viewport.setCamera( c.cam )
                }
            }
            if (voi) {
                this.viewports[0].setProperties({ voiRange: {lower:voi[0], upper:voi[1] }})
            }
        }
        // setVolumesForViewports(renderingEngine, [{ volumeId }], [viewportId]);
        // viewport.render();
        this.enableTools();
        // console.log("Volume starts loading");
        // const loading_finished = new Promise((resolve) => {
        //     this.volume.load( (e) => { console.log("Volume finished loading",e); resolve() });
        // });

        // await this.volume.load();
        this.renderingEngine.renderViewports(this.viewportIds);
        // return loading_finished
    }

    async setVolumeBySeries(series_uid) {
        console.log("Set volume by series", this.study_uid, series_uid)
        var { imageIds, metadata } = await cacheMetadata(
            { studyInstanceUID: this.study_uid,
                seriesInstanceUID: series_uid  },
            '/wado/'+this.case_id,
        );
        // console.log("Image IDs",imageIds)
        await this.setVolumeByImageIds(imageIds, series_uid, true);
    }
    startPreview() {
        console.info("Starting preview")
        this.previewViewports.slice(0,3).map((v, n) => {
            v.element.getElementsByTagName('svg')[0].innerHTML = this.viewports[n].element.getElementsByTagName('svg')[0].innerHTML
        });
    }
    async setPreview(idx, l) {
        try {
            requestIdleCallback( (()=>this.chart.renderGraph_()).bind(this))
            idx = parseInt(idx)
            let [lower, upper] = this.getVolumeVOI(this.viewports[0])

            this.previewViewports.slice(0,3).map(async (v, n) => {
                v.setVOI({lower, upper})
                await v.setImageIdIndex(Math.floor(idx * v.getImageIds().length / l))
            })
        } catch (e) {
            console.error(e);
        }
    }

    getVolumeVOI(viewport) {
        return viewport.getDefaultActor().actor.getProperty().getRGBTransferFunction(0).getRange()
    }
    async updatePreview(n=null, idx=0) {
        let update = [n]
        if (n==null){
            update = [0, 1, 2]
        }
        await Promise.all(update.map(async n => {
            let [lower, upper] = this.getVolumeVOI(this.viewports[0])
            this.previewViewports[n].setVOI({lower, upper})
            await this.setPreviewStackForViewport(n, this.previewViewports[n]) 
            this.previewViewports[n].setVOI({lower, upper})
        }))
    }
    async switchSeries(series_uid) {
        this.chart.renderGraph_()
        await this.setVolumeBySeries(series_uid);
        await new Promise( resolve => {
            this.volume.load( e => { console.log("Volume finished loading",e); resolve() });
        });
    }
    async switchStudy(info, case_id, keepCamera=true) {
        var [study_uid, dicom_set] = info;

        if (this.study_uid) {
            if (this.background_save_interval) 
                clearInterval(this.background_save_interval)
            this.saveState();
        }
        this.study_uid = study_uid;
        this.dicom_set = dicom_set;
        this.case_id = case_id
        this.selected_time = 0;
        var graspVolumeInfo = await (await fetch(`/api/case/${case_id}/dicom_set/${dicom_set}/study/${study_uid}/metadata`, {
            method: 'GET',   credentials: 'same-origin'
        })).json()
        document.getElementById("volume-picker").setAttribute("min",0)
        document.getElementById("volume-picker").setAttribute("max",graspVolumeInfo.length-1)
        document.getElementById("volume-picker").setAttribute("value",0)

        await this.setVolumeBySeries(graspVolumeInfo[0]["series_uid"]),
        this.volume.load(()=>{ 
            console.log("Volume loaded");
            this.loadState();
            if ( !this.background_save_interval ) {
                this.background_save_interval = this.backgroundSaveState()
            }
        })
        try {
            await this.updatePreview()
        } catch (e) {
            console.error(e);
        }

        console.log("Study switched");
        return graspVolumeInfo
    }

    async setPreviewStackForViewport(n, dest_viewport) {
        var viewport = this.viewports[n];
        var cam = viewport.getCamera()
    
        const volumeId = viewport.getActors()[0].uid;
        var volume = cornerstone.cache.getVolume(volumeId)
        var index = cornerstone.utilities.transformWorldToIndex(volume.imageData, cam.focalPoint)
        console.log(`Current view index: ${index}`);
        if (Math.abs(cam.viewPlaneNormal[0] == 1)) {
            var view = "SAG"
            var val = index[2]
        } else if (Math.abs(cam.viewPlaneNormal[1]) == 1) {
            var view = "COR"
            var val = index[0]
        } else if (Math.abs(cam.viewPlaneNormal[2]) == 1) {
            var view = "AX"
            var val = index[1]
        } else {
            return;
        }
        var info = await (
                await fetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/processed_results/CINE/${view}?slice_location=${val}`, {
            method: 'GET',   credentials: 'same-origin'
        })).json() 
        // console.log("Preview info:", info)
        // dest_viewport = dest_viewport? dest_viewport : this.viewports[3]
        // dest_viewport.setProperties( { voiRange: viewport.getProperties().voiRange });
        let [lower, upper] = this.getVolumeVOI(viewport);
        dest_viewport.setVOI({lower, upper})
        await dest_viewport.setStack(info.urls,dest_viewport.currentImageIdIndex);
        // console.log(cornerstone.requestPoolManager.getRequestPool().interaction)
        // cornerstone.tools.utilities.stackPrefetch.enable(dest_viewport.element);
    }
    getNativeViewports() {
        let native_viewports = [];
        for (var v of viewer.viewports) {
            let imageData = v.getDefaultImageData()
            if (!imageData) { continue; };
            let direction = imageData.getDirection().slice(-3);
            let normal = v.getCamera().viewPlaneNormal;
            let is_native = direction.every((v,i) => Math.abs(v) == Math.abs(normal[i]))
            if (is_native) {
                native_viewports.push(v.id);
            }
        }
        return native_viewports;
    }
    
}


window.onload = async function() {
    window.addEventListener( "error", ( error ) => {
        alert(`Unexpected error! \n\n ${error.message}`)
    })
}


export { GraspViewer, doJob };