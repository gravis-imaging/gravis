import { AnnotationManager } from "./annotations.js"
import { StateManager } from "./state.js"
import { doJob, viewportToImage, Vector, scrollViewportToPoint, doFetch } from "./utils.js"

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
      renderingEngine.resize(true, true);
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
    current_study;
    selected_time = 0;
    chart_options = {};

    findings;
    constructor( ...inp ) {
        return (async () => {
            await this.initialize(...inp);
            return this;
          })();   
         }
        async initialize( main, preview ) {
            // Force cornerstone to try to use GPU rendering even if it thinks the GPU is weak.
            cornerstone.setUseCPURendering(false);
            await cornerstone.helpers.initDemo(); 
            // Instantiate a rendering engine
            const renderingEngineId = 'gravisRenderEngine';
            this.renderingEngine = new cornerstone.RenderingEngine(renderingEngineId);    
    
            const ORIENTATION = cornerstone.CONSTANTS.MPR_CAMERA_VALUES;
    
            const preview_info = [["AX"],["SAG"],["COR"]]
            const [ previewViewports, previewViewportIds ] = this.createViewports("PREVIEW",preview_info, preview)
            
            const view_info = [["AX",  ORIENTATION.axial],
                               ["SAG", ORIENTATION.sagittal],
                               ["COR", {"viewPlaneNormal": [0,1,0],
                                        "viewUp": [0,0,1]}]]
            const [ viewViewports, viewportIds ] = this.createViewports("VIEW", view_info, main)
            
            // Expand a viewport to fill the entire left part of the grid.
            for (const [index, v] of viewViewports.entries()){
                v.element.ondblclick = e => {
                    let el = v.element;
                    let pre_el = this.renderingEngine.getViewport("PRE"+v.viewportId).element
                    let overlay_el = document.getElementById(`viewport-overlay-${index+1}`)
                    if (el.getAttribute("fullscreen") != "true") {
                        [...document.getElementsByClassName("viewport-overlay")].map(
                                el => { if (el!=overlay_el) el.style.display = "none" }
                            )
                        el.setAttribute("fullscreen", "true");
                        el.setAttribute("orig-column", el.style.gridColumn)
                        for (const _el of [el,pre_el,overlay_el]) {
                            _el.style.zIndex = 1;
                            _el.style.gridArea = "1 / 1 / 1 / -1";
                        }
                        document.getElementById("grasp-view-outer").style.gridArea = "e / e / f / f"
                    } else {
                        el.removeAttribute("fullscreen");
                        for (const _el of [el,pre_el,overlay_el]) {
                            _el.style.gridArea = "";
                            _el.style.gridRow = 1;
                            _el.style.gridColumn = el.getAttribute("orig-column");
                            _el.style.zIndex = 0;
                        }
                        [...document.getElementsByClassName("viewport-overlay")].map(el => el.style.display = "block")
                        document.getElementById("grasp-view-outer").style.gridArea = "e"
                    }
                }
            }

            const auxViewport = this.genViewportDescription("AUX", null, document.getElementById("aux-container"), "VIEW")

            auxViewport.element.ondblclick = e => {
                const el = auxViewport.element;
                if (el.getAttribute("fullscreen") != "true") {
                    el.setAttribute("fullscreen", "true");
                    el.style.gridArea = "e / e / f / f";
                    el.style.zIndex = 1;
                } else {
                    el.removeAttribute("fullscreen");
                    el.style.gridArea = "d";
                    el.style.zIndex = 0;
                }
                this.renderingEngine.resize(true, true);
            }
            auxViewport.element.oncontextmenu = e=>e.preventDefault();

            this.renderingEngine.setViewports([...previewViewports, ...viewViewports, auxViewport])
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
            
            cornerstone.eventTarget.addEventListener("CORNERSTONE_TOOLS_ANNOTATION_MODIFIED",(evt) => { 
                if (this.state_manager.just_loaded) { 
                    // Loading annotations seems to emit this event, so we'll ignore the first one after a load
                    this.state_manager.just_loaded = false;
                    return;
                }
                this.state_manager.setChanged();
            });
            // Prompt the user if there are unsaved changes.
            // TODO: this is a bit overzealous, just mousing over an annotation can trigger a "modified" event.
            addEventListener('beforeunload', (event) => { if (this.state_manager.changed) { event.returnValue = "ask"; return "ask"; } });

            cornerstone.eventTarget.addEventListener("CORNERSTONE_TOOLS_ANNOTATION_MODIFIED",debounce(100, (evt) => {
                this.annotation_manager.updateChart()
            }));
            
            // Highlight selected annotation on the chart
            cornerstone.eventTarget.addEventListener("CORNERSTONE_TOOLS_ANNOTATION_SELECTION_CHANGE", (evt) => {
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

            // Synchronize the preview viewports
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
            el.style.gridColumn = i+1;
            el.style.gridRow = 1;
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
        toolGroupAux.setToolActive(Tools.PanTool.toolName, {
            bindings: [{ 
                mouseButton: Enums.MouseBindings.Primary,
                modifierKey: Enums.KeyboardBindings.Alt,
            }],
        });
        toolGroupAux.setToolActive(Tools.ZoomTool.toolName, {
            bindings: [{ 
                mouseButton: Enums.MouseBindings.Secondary,
                modifierKey: Enums.KeyboardBindings.Alt,
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
    async setPreview(idx) {
        try {
            this.switchMIP(idx);
        } catch (e) {};

        try {
            requestIdleCallback( (()=>this.chart.renderGraph_()).bind(this))
            idx = parseInt(idx)
            let [lower, upper] = this.getVolumeVOI(this.viewports[0])

            this.previewViewports.slice(0,3).map(async (v, n) => {
                v.setVOI({lower, upper})
                await v.setImageIdIndex(Math.floor(idx * v.getImageIds().length / this.current_study.length))
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
            this.previewViewports[n].setVOI({lower, upper});
            await this.setPreviewStackForViewport(n, this.previewViewports[n]) 
            this.previewViewports[n].setVOI({lower, upper});
        }))
    }
    async switchSeries(series_uid) {
        this.chart.renderGraph_()
        await this.setVolumeBySeries(series_uid);
        await new Promise( resolve => {
            this.volume.load( e => { console.log("Volume finished loading",e); resolve() });
        });
    }
    async switchMIP(index) {
        const current_info = this.current_study[index];
        const viewport = this.renderingEngine.getViewport('VIEW_AUX');
        const ori_dicom_set = studies_data_parsed.find((x)=>x[2]=="ORI")[1]
        const mip_urls = (await doFetch(`/api/case/${this.case_id}/dicom_set/${ori_dicom_set}/processed_results/MIP?acquisition_number=${current_info.acquisition_number}`,null, "GET")).urls;

        const cam = viewport.getCamera();
        if ( mip_urls.length > 0 ) {
           await viewport.setStack(mip_urls, viewport.targetImageIdIndex);
           if (!cam.focalPoint.every( k => k==0 )) viewport.setCamera(cam);
           viewport.render()
        }
    }
    async switchToIndex(index) {
        const current_info = this.current_study[index];
        await this.switchMIP(index);
        await viewer.switchSeries(current_info.series_uid); 
        this.selected_time = current_info.acquisition_seconds; 
    }
    async switchStudy(info, case_id, keepCamera=true) {
        const [study_uid, dicom_set] = info;

        this.study_uid = study_uid;
        this.dicom_set = dicom_set;
        this.case_id = case_id

        if (! this.selected_time ) {            
            await this.state_manager.load();
            this.findings = await this.loadFindings();
        }

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
        } else {
            this.selected_time = graspVolumeInfo[0].acquisition_seconds;
        }
        console.log(`Loading index ${selected_index}`)
        console.log(graspVolumeInfo)
        await this.setVolumeBySeries(graspVolumeInfo[selected_index]["series_uid"])
        document.getElementById("volume-picker").setAttribute("value",selected_index)

        this.volume.load(async ()=>{ 
            console.log("Volume loaded");
        })
        try {
            await this.updatePreview();
        } catch (e) {
            console.error(e);
        }

        console.log("Study switched");
        this.current_study = graspVolumeInfo;
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
    async loadFindings() {
        const result = await doFetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/finding`,{},"GET");
        return result.findings;
    }
    async storeFinding(viewport){
        // const viewport = this.viewports[n];
        const image = await viewportToImage(viewport);

        const info = {
            cam: viewport.getCamera(), //this.viewports.map(v=>v.getCamera()),
            viewportId: viewport.id,
            time: this.selected_time,
            imageIdIndex: viewport.currentImageIdIndex? viewport.currentImageIdIndex : null
            // center_index: cornerstone.utilities.transformWorldToIndex(viewport.getDefaultImageData(), viewport.getCamera().focalPoint),
        }
        const result = await doFetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/finding`, {image_data: image, info: info});
        this.findings.push(result);
    }
    async deleteFinding(id){
        const result = await doFetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/finding/${id}`,{}, "DELETE");
        this.findings = await this.loadFindings()
    }
    async renameFinding(finding){
        let prompt_result = prompt("Finding name?")
        if (! prompt_result ) return;
        prompt_result = prompt_result.trim();
        if (! prompt_result ) return;
        finding.name = prompt_result;
        const result = await doFetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/finding/${finding.id}`,{name:finding.name}, "PATCH");
        // this.findings = await this.loadFindings()
    }
    async goToFinding(finding) {
        if (finding.data.viewportId != "VIEW_AUX") {
            for (const v of this.viewports) {
                const view_cam = v.getCamera();
                if (Vector.eq(view_cam.viewPlaneNormal, finding.data.cam.viewPlaneNormal)) {
                    scrollViewportToPoint(v, finding.data.cam.focalPoint);
                    cornerstone.tools.utilities.triggerAnnotationRenderForViewportIds(this.renderingEngine,this.viewportIds) 
                    this.renderingEngine.renderViewports(this.viewportIds);
                    break;
                }
            }
        }
        let new_selected_time;
        let new_selected_index;
        let new_selected_series;
        for (const [index, info] of this.current_study.entries()) { 
            if ( Math.abs(info.acquisition_seconds - finding.data.time) < 0.001 ) {
                new_selected_time = info.acquisition_seconds;
                new_selected_index = index;
                new_selected_series = info.series_uid
                break;
            }
        }

        for (const [index, info] of studies_data_parsed.entries()) {
            if (info[1] === finding.dicom_set && info[1] != this.dicom_set){
                for (const [index, info] of this.current_study.entries()) { 
                    if ( Math.abs(info.acquisition_seconds - finding.data.time) < 0.001 ) {
                        this.selected_time = info.acquisition_seconds;
                    }
                }
                this.selected_time = new_selected_time;
                document.getElementById("volume-picker").value = new_selected_index;
                await this.switchStudy(info.slice(0,2),this.case_id);
                return;
            }
        }
        // if (finding.data.viewportId = "VIEW_AUX") {
        //     await this.switchMIP(new_selected_index);
        //     console.log("Going to AUX")
        //     const v = viewer.renderingEngine.getViewport("VIEW_AUX");
        //     await v.setImageIdIndex(finding.data.imageIdIndex);
        //     v.setCamera(finding.data.cam);
        //     v.render();
        // }
        if (new_selected_time != this.selected_time) {
            this.selected_time = new_selected_time;
            document.getElementById("volume-picker").value = new_selected_index;
            await this.switchToIndex(new_selected_index); 
        }
    }
}


window.onload = async function() {
    window.addEventListener( "error", ( error ) => {
        if (error.message.indexOf("ResizeObserver") != -1) { return;}
        alert(`Unexpected error! \n\n ${error.message}`)
    })
}


export { GraspViewer, doJob, viewportToImage };