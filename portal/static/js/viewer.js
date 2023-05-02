import { AnnotationManager } from "./annotations.js"
import { StateManager } from "./state.js"
import { MIPManager, AuxManager } from "./mip.js"
import { debounce, doJob, viewportToImage, Vector, scrollViewportToPoint, doFetch, loadVolumeWithRetry, chartToImage, successToast, fixUpCrosshairs,decacheVolumes, errorPrompt, errorToast } from "./utils.js"


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
  ) {    
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

class GraspViewer {
    renderingEngine;
    viewportIds = [];
    previewViewportIds = [];

    viewports = [];
    previewViewports = [];
    studies_data = [];

    chart;
    toolsAlreadyActive = false;

    dicom_set;
    case_id;
    study_uid;
    volume; 
    current_study;
    selected_time = 0;
    chart_options = {mode: "mean", adjust:"standard"};
    case_type = "MRA";

    mip_details = [];

    findings;
    
    rotate_mode = false;

    constructor( ...inp ) {
        return (async () => {
            await this.initialize(...inp);
            return this;
          })();   
        }

        async initialize( main, preview, studies_data, case_data ) {
            this.studies_data = studies_data;
            this.case_data = case_data;
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
                               ["COR", ORIENTATION.coronal]]
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

            if (case_data.case_type == "GRASP MRA") {
                this.aux_manager = new MIPManager(this);
            } else {
                this.aux_manager = new AuxManager(this);
            }
            this.renderingEngine.setViewports([...previewViewports, ...viewViewports]);
            this.viewportIds = [...viewportIds];
            this.previewViewportIds = previewViewportIds;
            this.viewports = this.viewportIds.map((c)=>this.renderingEngine.getViewport(c));

            await this.aux_manager.createViewport();
            this.auxViewport = this.aux_manager.viewport;
            this.viewportIds.push(this.aux_manager.viewport.id)
            this.previewViewports = previewViewportIds.map((c)=>this.renderingEngine.getViewport(c));
            this.annotation_manager = new AnnotationManager(this);
            this.state_manager = new StateManager(this);

            
            cornerstone.tools.synchronizers.createVOISynchronizer("SYNC_CAMERAS");
            this.createTools();
            this.renderingEngine.renderViewports([...this.viewportIds, ...this.previewViewports]);
            this.chart = this.annotation_manager.initChart();
                       
            // cornerstone.eventTarget.addEventListener(cornerstone.Enums.Events.IMAGE_LOAD_ERROR, (evt) => {
            //     console.error("Image load error", evt)
            // })
            // cornerstone.eventTarget.addEventListener(cornerstone.Enums.Events.IMAGE_LOAD_FAILED, (evt) => {
            //     console.error("Image load failed", evt)
            // })

            cornerstone.eventTarget.addEventListener(cornerstone.tools.Enums.Events.ANNOTATION_MODIFIED,debounce(100, (evt) => {
                this.annotation_manager.updateChart();
            }));
            
            // Highlight selected annotation on the chart
            cornerstone.eventTarget.addEventListener(cornerstone.tools.Enums.Events.ANNOTATION_SELECTION_CHANGE, (evt) => {
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
                v.element.addEventListener(cornerstone.Enums.Events.CAMERA_MODIFIED, debounce(250, async (evt) => {
                    if (! v.getDefaultActor() ) return;
                    if ( this.rotate_mode ) return;
                    try {
                        await this.updatePreview(n)
                        this.previewViewports[n].setZoom(v.getZoom());
                        this.previewViewports[n].setPan(v.getPan());
                        this.previewViewports[n].render();
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
            // Add class to display border on the right side between viewers except the last one
            el.className = "viewer-element viewer-element-border"
            if (i==n-1) {
                el.className = "viewer-element"
            }
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

    resetCameras() {
        for (const v of this.viewports) {
            v.resetCamera();
        }
        fixUpCrosshairs();
        this.renderingEngine.renderViewports(this.viewportIds);
    }
    createTools() {
        const cornerstoneTools = window.cornerstone.tools;

        const {
            PanTool,
            ZoomTool,
            WindowLevelTool,
            StackScrollMouseWheelTool,
            StackScrollTool,
            VolumeRotateMouseWheelTool,
            ToolGroupManager,
            CrosshairsTool,
            EllipticalROITool,
            ProbeTool,
            Enums: csToolsEnums,
        } = cornerstoneTools;

        const { MouseBindings } = csToolsEnums;
        const tools = [CrosshairsTool, EllipticalROITool, StackScrollMouseWheelTool, StackScrollTool, VolumeRotateMouseWheelTool, WindowLevelTool, PanTool, ZoomTool, ProbeTool]
        tools.map(cornerstoneTools.addTool)
        // Define a tool group, which defines how mouse events map to tool commands for
        // Any viewport using the group
        const toolGroupMain = ToolGroupManager.createToolGroup(`STACK_TOOL_GROUP_MAIN`);
        const toolGroupAux = ToolGroupManager.createToolGroup(`STACK_TOOL_GROUP_AUX`);

        const allGroupTools = [ WindowLevelTool.toolName, PanTool.toolName, ZoomTool.toolName ]
        for (var viewport of this.viewportIds.slice(0,3)) {
            toolGroupMain.addViewport(viewport, "gravisRenderEngine");
        }

        toolGroupAux.addViewport(this.viewportIds[3], "gravisRenderEngine");
        allGroupTools.map( tool => [toolGroupMain, toolGroupAux].map(group => group.addTool(tool)))
        
        toolGroupMain.addTool(StackScrollMouseWheelTool.toolName)
        
        toolGroupAux.addTool(StackScrollTool.toolName, {loopScroll: true});
        toolGroupAux.addTool(StackScrollMouseWheelTool.toolName, {loopScroll: true});
        
        [toolGroupMain, toolGroupAux].map(x=>x.addTool(ProbeTool.toolName, {
            customTextLines: (data) => [ data.label ]
        }));

        [toolGroupMain, toolGroupAux].map(x=>x.addTool(EllipticalROITool.toolName, {
            centerPointRadius: 1,
            customTextLines: (data) => [ data.label ]
        }));
        
        var styles = cornerstone.tools.annotation.config.style.getDefaultToolStyles()
        styles.global.lineWidth = "1"
        cornerstone.tools.annotation.config.style.setDefaultToolStyles(styles)
        toolGroupMain.addTool(CrosshairsTool.toolName, {
            getReferenceLineColor: (id) => { return ({"VIEW_AX": "rgb(255, 255, 100)",
                                                      "VIEW_SAG": "rgb(18, 102, 241)",
                                                      "VIEW_COR": "rgb(255, 100, 100)",})[id]},
            getReferenceLineRotatable: (id) => this.rotate_mode,
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
        [toolGroupMain, toolGroupAux].map(g=>{
            g.setToolActive(Tools.WindowLevelTool.toolName, {
                bindings: [{ 
                    mouseButton: Enums.MouseBindings.Primary,
                    modifierKey: Enums.KeyboardBindings.Ctrl,
                }],}
            )
            g.setToolActive(Tools.ZoomTool.toolName, {
                bindings: [{ 
                    mouseButton: Enums.MouseBindings.Secondary,
                    modifierKey: Enums.KeyboardBindings.Alt,
                }],
            });
            g.setToolActive(Tools.PanTool.toolName, {
                bindings: [{ 
                    mouseButton: Enums.MouseBindings.Primary,
                    modifierKey: Enums.KeyboardBindings.Alt,
                }],
            });
        });

        [toolGroupMain, toolGroupAux].map(x=>x.setToolPassive(Tools.EllipticalROITool.toolName, {
            bindings: [
                {
                    mouseButton: Enums.MouseBindings.Primary,
                },
            ],
        }));

        [toolGroupMain, toolGroupAux].map(x=>x.setToolPassive(Tools.ProbeTool.toolName, {
            bindings: [
                {
                    mouseButton: Enums.MouseBindings.Primary,
                },
            ],
        }));

        toolGroupAux.setToolActive(Tools.StackScrollTool.toolName,{
            bindings: [
                {
                    mouseButton: Enums.MouseBindings.Primary,
                },
        ]});

        toolGroupMain.setToolActive(Tools.StackScrollMouseWheelTool.toolName)
        toolGroupAux.setToolActive(Tools.StackScrollMouseWheelTool.toolName)
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

        decacheVolumes();
        this.volume = await cornerstone.volumeLoader.createAndCacheVolume(volumeId, { imageIds });
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
                    c.viewport.setCamera( c.cam );
                }
            }
            if (voi) {
                this.viewports[0].setProperties({ voiRange: {lower:voi[0], upper:voi[1] }})
            }
            fixUpCrosshairs();
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
    
    startPreview(idx) {
        this.previewViewports.slice(0,3).map((v, n) => {
            v.element.getElementsByTagName('svg')[0].innerHTML = this.viewports[n].element.getElementsByTagName('svg')[0].innerHTML
        });
        this.snapToSlice();
    }

    async setPreview(idx) {
        try {
            requestAnimationFrame( (()=>this.chart.renderGraph_()).bind(this))
            idx = parseInt(idx)
            let [lower, upper] = this.getVolumeVOI(this.viewports[0])

            await Promise.all(
                this.previewViewports.slice(0,3).map(async (v, n) => {
                v.setVOI({lower, upper});
                // Get closest preview image if only fraction of preview images were generated.
                try {
                    await v.setImageIdIndex(Math.floor(idx * v.getImageIds().length / this.current_study.length));
                } catch (e) {
                    console.error(e);
                    await errorToast("Failed to show preview image.");
                }
            }))
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
            // console.log("Volume VOI", upper,lower)
            this.previewViewports[n].setVOI({lower, upper});
            try {
                await this.setPreviewStackForViewport(n, this.previewViewports[n]) 
            } catch (e) {
                console.error(e);
                await errorToast("Failed to set preview stack.");
            }
            this.previewViewports[n].setVOI({lower, upper});
        }))
    }

    async switchSeries(series_uid) {
        this.chart.renderGraph_();
        await this.setVolumeBySeries(series_uid);
        const volume_result = await loadVolumeWithRetry(this.volume);
        this.fixShift();
    }    

    async switchToIndex(index) {
        // window.history.replaceState(null, null, `#selected_index=${index}`);
        const current_info = this.current_study[index];
        await viewer.switchSeries(current_info.series_uid); 
        this.selected_time = current_info.acquisition_seconds; 
    }

    snapToSlice() {
        for ( var i=0;i<3;i++) {
            cornerstone.tools.utilities.scroll(viewer.viewports[i],{delta:0,volumeId:viewer.viewports[i].getDefaultActor().uid})
            viewer.viewports[i].render();
        }
        fixUpCrosshairs()
    }
    fixShift() {
        for ( var i=0; i<3; i++) {
            // This tries to align the centers of the viewports and the preview viewports.
            let center_a = this.viewports[i].worldToCanvas(this.viewports[i].getDefaultActor().actor.getCenter());
            let center_b = this.previewViewports[i].worldToCanvas(this.previewViewports[i].getDefaultActor().actor.getCenter());
            let shift = Vector.sub(center_b, center_a);
            this.viewports[i].setPan(shift,true);
            this.viewports[i].render();
        }
        fixUpCrosshairs()
    }
    async switchStudy(study_uid, dicom_set, case_id, keepCamera=true) {       
        this.study_uid = study_uid;
        this.dicom_set = dicom_set;
        this.case_id = case_id

        if (! this.selected_time ) {            
            await this.state_manager.load();
            this.findings = await this.loadFindings();
        }

        const graspVolumeInfo = await doFetch(`/api/case/${case_id}/dicom_set/${dicom_set}/study/${study_uid}/metadata`, {}, "GET")

        document.getElementById("volume-picker").setAttribute("min",0)
        document.getElementById("volume-picker").setAttribute("max",graspVolumeInfo.length-1)

        let selected_index = 0
        // console.log(`Selected time: ${this.selected_time}`)
        
        // Try to select the same time point as we are currently on
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
        // console.log(`Loading index ${selected_index}`)
        // console.log(graspVolumeInfo)
        await this.setVolumeBySeries(graspVolumeInfo[selected_index]["series_uid"])
        document.getElementById("volume-picker").setAttribute("value",selected_index)        
        
        this.current_study = graspVolumeInfo;
         
        this.aux_manager.init(graspVolumeInfo, selected_index);

        const volume_result = await loadVolumeWithRetry(this.volume);
        
        try {
            await this.updatePreview();
        } catch (e) {
            console.error(e);
        }
        this.fixShift();
        
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

        const view = ["SAG", "COR", "AX"][cam.viewPlaneNormal.findIndex(x=>Math.abs(x)==1)];
        const cine_urls = await doFetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/preview/${view}/${index.join()}`, {}, "GET")
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

    toggleRotateMode() {
        this.rotate_mode = !this.rotate_mode;
        if (this.rotate_mode) { 
            return;
        }
        const ORIENTATION = cornerstone.CONSTANTS.MPR_CAMERA_VALUES;        
        const orientations = { "VIEW_AX": ORIENTATION.axial, "VIEW_SAG":  ORIENTATION.sagittal, "VIEW_COR": ORIENTATION.coronal}

        const mainTools = cornerstone.tools.ToolGroupManager.getToolGroup("STACK_TOOL_GROUP_MAIN");
        const toolCenter = mainTools.getToolInstance(cornerstone.tools.CrosshairsTool.toolName).toolCenter;

        for (var v of this.viewports) {
            const new_camera = JSON.parse(JSON.stringify(v.getCamera()));
            new_camera.focalPoint = toolCenter;
            let orientation = orientations[v.id];
            // First position the the camera relative to the crosshairs center, then fix the pan. 
            // This is probably not the most direct way to do it, but it seems to work reliably.
            const pan = v.getPan();
            const dist = Vector.len(Vector.sub(new_camera.focalPoint, new_camera.position));
            const position = Vector.add(new_camera.focalPoint,Vector.mul(orientation.viewPlaneNormal,dist));
            v.setCamera({...new_camera, ...orientation, position});
            v.setPan(pan);
            v.render();
        }
        fixUpCrosshairs()
        cornerstone.tools.utilities.triggerAnnotationRenderForViewportIds(this.renderingEngine,this.viewportIds);
    }
    async loadFindings() {
        const result = await doFetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/finding`,{},"GET");
        return result.findings;
    }
    async storeChartFinding() {
        const image = await chartToImage(this.chart);
        const info = {
            time: this.selected_time,
        }
        const result = await doFetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/finding`, {image_data: image, info: info});
        this.findings.push(result);        
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
        try {
            const result = await doFetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/finding`, {image_data: image, data: info});
            this.findings.push(result);
        } catch(e) { 
            errorPrompt("Failed to create finding.")
        }
    }

    async deleteFinding(id){
        const result = await doFetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/finding/${id}`,{}, "DELETE");
        this.findings = await this.loadFindings()
    }

    async renameFinding(finding){

        const { value: input_value } = await Swal.fire({
            input: 'text',
            inputLabel: 'Finding Description',
            inputPlaceholder: 'Describe the finding here...',
            showCancelButton: true,
            inputValidator: (value) => {
                if (!value) {
                    return "Please provide a description";
                }
                if (value.length > 100) {
                    return "The description must be fewer than 100 characters.";
                }
            },
            preConfirm: async (value) => {
                try {
                    await doFetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/finding/${finding.id}`,{name:value}, "PATCH");
                    finding.name = value;
                } catch (e) {
                    Swal.showValidationMessage("A problem occurred while editing this finding. Please try again.")
                }
            },
            ...(finding.name? {inputValue: finding.name}: {})
        })
        // this.findings = await this.loadFindings()
    }

    async transferFindings() {
        try {
            // TODO: This waits until the findings are actually transmitted to show a success. 
            // Under load this might actually take a while. 
            const result = await doJob("send_findings", this.case_id,{}, true);
            successToast("Transmitted findings.");
        } catch (e) {
            console.error(e);
            errorToast("Findings submission failed.");
            return false;
        }
        return true;
    }

    async goToFinding(finding) {
        for (const v of this.viewports.slice(0,3)) {
            const view_cam = v.getCamera();
            if (Vector.eq(view_cam.viewPlaneNormal, finding.data.cam.viewPlaneNormal)) {
                scrollViewportToPoint(v, finding.data.cam.focalPoint);
                cornerstone.tools.utilities.triggerAnnotationRenderForViewportIds(this.renderingEngine,this.viewportIds) 
                this.renderingEngine.renderViewports(this.viewportIds);
                break;
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

        for (const [index, info] of this.studies_data.volumes.entries()) {
            if (info.dicom_set === finding.dicom_set && info.dicom_set != this.dicom_set){
                for (const [index, info] of this.current_study.entries()) { 
                    if ( Math.abs(info.acquisition_seconds - finding.data.time) < 0.001 ) {
                        this.selected_time = info.acquisition_seconds;
                    }
                }
                this.selected_time = new_selected_time;
                document.getElementById("volume-picker").value = new_selected_index;
                await this.switchStudy(info.uid, info.dicom_set,this.case_id);
                return;
            }
        }
       
        if (new_selected_time != this.selected_time) {
            this.selected_time = new_selected_time;
            document.getElementById("volume-picker").value = new_selected_index;
            await Promise.all([
                this.aux_manager.switch(new_selected_index, false, finding.data.imageIdIndex),
                this.switchToIndex(new_selected_index)])
        } 
    }

    async showFinding(finding) {
        const el = document.getElementById('finding_modal');
        const modal = new mdb.Modal(el)
        modal.show();
        document.getElementById("finding_modal_img").setAttribute("src",finding.url)
        document.getElementById("finding_modal_description").innerText = finding.name;
    }
}


window.onload = async function() {
    window.addEventListener( "error", ( error ) => {
        if (error.message.indexOf("ResizeObserver") != -1) { return;}
        alert(`Unexpected error! \n\n ${error.message}`)
    })
}


export { GraspViewer, doJob, viewportToImage };
