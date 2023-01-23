import { AnnotationManager } from "./annotations.js"
import { StateManager } from "./state.js"
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
    // metadata = metadata.sort((a,b) => getMeta(a,'00200013') < getMeta(b,'00200013'))
    let imageIds = []
    for (var instanceMetaData of metadata) {
        let imageId = getImageId(instanceMetaData, wadoRsRoot);
        // cornerstone.cornerstoneWADOImageLoader.wadors.metaDataManager.add(
        //   imageId,
        //   instanceMetaData
        // );
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
        async initialize( main, preview ) {
            const { RenderingEngine, Types, Enums, volumeLoader, CONSTANTS, setVolumesForViewports} = window.cornerstone; 
            const { ViewportType } = Enums;
            // Force cornerstone to try to use GPU rendering even if it thinks the GPU is weak.
            cornerstone.setUseCPURendering(false);
            await cornerstone.helpers.initDemo(); 
            // Instantiate a rendering engine
            const renderingEngineId = 'gravisRenderEngine';
            this.renderingEngine = new RenderingEngine(renderingEngineId);    
    
            const ORIENTATION = cornerstone.CONSTANTS.MPR_CAMERA_VALUES;
    
            const preview_info = [["AX"],["SAG"],["COR"]]
            const [ previewViewports, previewViewportIds ] = this.createViewports("PREVIEW",preview_info, preview)
            /*
            ["COR",{
                                sliceNormal: [ 0, -1, 0 ],
                                viewUp: [ 0, 0, 1 ]
            }],*/
            
            const view_info = [["AX",ORIENTATION.axial],["SAG",ORIENTATION.sagittal],["COR",
            {"viewPlaneNormal": [0,1,0],
                "viewUp": [0,0,1]}]]
            const [ viewViewports, viewportIds ] = this.createViewports("VIEW", view_info, main)


            const auxViewport = this.genViewportDescription("CINE", null, document.getElementById("aux-container"), "VIEW")

            // const [ [auxViewport], [auxViewportId]] = this.createViewports("VIEW", [["CINE"]], document.getElementById("aux-container"))
            // document.getElementById("aux-container").firstChild.style="grid-template-columns: 1fr"
            // document.getElementById("aux-container")
            this.renderingEngine.setViewports([...previewViewports,, ...viewViewports,  auxViewport])
    
            this.viewportIds = [...viewportIds , auxViewport.viewportId]
            this.previewViewportIds = previewViewportIds
            this.viewports = viewportIds.map((c)=>this.renderingEngine.getViewport(c))
            this.previewViewports = previewViewportIds.map((c)=>this.renderingEngine.getViewport(c))

            this.annotation_manager = new AnnotationManager(this)
            this.state_manager = new StateManager(this)

            cornerstone.tools.synchronizers.createVOISynchronizer("SYNC_CAMERAS");
            this.createTools();
            this.renderingEngine.renderViewports([...this.viewportIds, ...this.previewViewports]);
            this.chart = this.annotation_manager.initChart();

            cornerstone.eventTarget.addEventListener("CORNERSTONE_TOOLS_ANNOTATION_MODIFIED",debounce(100, (evt) => {
                this.annotation_manager.updateChart()
            }));
            cornerstone.eventTarget.addEventListener("CORNERSTONE_TOOLS_ANNOTATION_SELECTION_CHANGE",(evt) => {
                // console.log();
                const detail = evt.detail;
                if (detail.selection.length == 1) {
                    const uid = detail.selection[0];
                    const annot = cornerstone.tools.annotation.state.getAnnotation(uid)
                    this.chart.setSelection(false, annot.data.label, true);
                } else {
                    this.chart.clearSelection();
                }
                this.chart.renderGraph_()
            });
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
            });
        }
    
    
    createViewportGrid(n=4) {
        const viewportGrid = document.createElement('div');
        viewportGrid.className = 'viewer-grid';
        var elements = [];
        for (var i=0; i<n; i++) {
            var el = document.createElement('div');
            el.className = "viewer-element"
            viewportGrid.appendChild(el);
            elements.push(el)
            resizeObserver.observe(el);
            el.oncontextmenu = e=>e.preventDefault();
        }
        return [viewportGrid, elements];
    }
    
    genViewportDescription(viewportId, orientation, element, prefix, background = [0,0,0]) {
        return {
            viewportId: prefix + "_" + viewportId,
            type: orientation ? cornerstone.Enums.ViewportType.ORTHOGRAPHIC : cornerstone.Enums.ViewportType.STACK,
            element: element,
            defaultOptions: {
                orientation,
                background
            },
        }
    }

    createViewports( prefix, list, parent, background) {
        const [viewportGrid, viewportElements] = this.createViewportGrid(list.length)
        parent.appendChild(viewportGrid);
        var viewportInput = list.map(([viewportId, orientation],n) => {
            return this.genViewportDescription(viewportId, orientation, viewportElements[n], prefix, background)
            });
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
            EllipticalROITool,
            ProbeTool,
            Enums: csToolsEnums,
        } = cornerstoneTools;
        const { MouseBindings } = csToolsEnums;
        const tools = [CrosshairsTool, EllipticalROITool, StackScrollMouseWheelTool, VolumeRotateMouseWheelTool, WindowLevelTool, PanTool, ZoomTool, ProbeTool]
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

        toolGroupMain.addTool(ProbeTool.toolName, {
            customTextLines: (data) => [ data.label ]
        });
        toolGroupMain.addTool(EllipticalROITool.toolName,
            {
                centerPointRadius: 1,
                customTextLines: (data) => [ data.label ]
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

        toolGroupMain.setToolPassive(Tools.EllipticalROITool.toolName, {
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
            console.log("Volume VOI", upper,lower)
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
        const [study_uid, dicom_set] = info;

        if (this.study_uid) {
            this.state_manager.stopBackgroundSave();
            this.state_manager.save();
        }
        this.study_uid = study_uid;
        this.dicom_set = dicom_set;
        this.case_id = case_id

        const graspVolumeInfo = await (await fetch(`/api/case/${case_id}/dicom_set/${dicom_set}/study/${study_uid}/metadata`, {
            method: 'GET',   credentials: 'same-origin'
        })).json()

        document.getElementById("volume-picker").setAttribute("min",0)
        document.getElementById("volume-picker").setAttribute("max",graspVolumeInfo.length-1)

        let selected_index = 0
        console.log(`Selected time: ${this.selected_time}`)
        if ( this.selected_time ) {
            for (const [index, info] of graspVolumeInfo.entries()) { 
                if ( Math.abs(info.acquisition_seconds - this.selected_time) < 0.001 ) {
                    selected_index = index;
                    this.selected_time = info.acquisition_seconds;
                    break;
                }
            }
        }
        console.log(`Loading index ${selected_index}`)
        console.log(graspVolumeInfo)
        await this.setVolumeBySeries(graspVolumeInfo[selected_index]["series_uid"])
        document.getElementById("volume-picker").setAttribute("value",selected_index)


        this.volume.load(()=>{ 
            console.log("Volume loaded");
            this.state_manager.load();
            this.state_manager.startBackgroundSave();
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
        const viewport = this.viewports[n];
        const cam = viewport.getCamera();
    
        const volumeId = viewport.getActors()[0].uid;
        const volume = cornerstone.cache.getVolume(volumeId);
        // const info = await doFetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/processed_json/CINE`);
        const index = cornerstone.utilities.transformWorldToIndex(volume.imageData, cam.focalPoint);

        const view = ["SAG", "COR","AX"][cam.viewPlaneNormal.findIndex(x=>Math.abs(x)==1)];
        const cine_urls = await (
            await fetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/preview/${view}/${index.join()}`, {
            method: 'GET',   credentials: 'same-origin'
        })).json();
        // console.log("Preview info:", info)
        // dest_viewport = dest_viewport? dest_viewport : this.viewports[3]
        // dest_viewport.setProperties( { voiRange: viewport.getProperties().voiRange });
        let [lower, upper] = this.getVolumeVOI(viewport);
        dest_viewport.setVOI({lower, upper});
        await dest_viewport.setStack(cine_urls.urls,dest_viewport.currentImageIdIndex);
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
        if (error.message.indexOf("ResizeObserver") != -1) { return;}
        alert(`Unexpected error! \n\n ${error.message}`)
    })
}


export { GraspViewer, doJob };