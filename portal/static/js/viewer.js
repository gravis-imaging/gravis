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
    annotations = {};
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
        const annotations = this.getAllAnnotations();
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
        console.info("Loading state.");
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
                old_annotations = this.getAllAnnotations(v);
                if (!old_annotations) continue;
                for (let a of old_annotations) {
                    annotationState.removeAnnotation(a.annotationUID, v.element)
                }
            }
            for (var a of Object.keys(this.annotations)) {
                delete this.annotations[a];
            }
            for (var a of state.annotations) {
                this.annotations[a.annotationUID] = { uid: a.annotationUID, label: a.data.label, ...a.metadata }
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
            // renderingEngine.enableElement(viewportInput);
            cornerstone.tools.synchronizers.createVOISynchronizer("SYNC_CAMERAS");
            this.createTools();
            this.renderingEngine.renderViewports([...this.viewportIds, ...this.previewViewports]);
            this.chart = this.initChart();

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
                    this.updateChart()
                }));
            });
    
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
    
        this.viewports.map(v=>v.element.oncontextmenu = e=>e.preventDefault())
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
        // console.log("VOI", lower,upper)
        
    }

    getVolumeVOI(viewport) {
        return viewport.getDefaultActor().actor.getProperty().getRGBTransferFunction(0).getRange()
    }
    async updatePreview(n=null, idx=0) {
        // console.log("Updating previews...")
        let update = [n]
        if (n==null){
            update = [0, 1, 2]
        }
        await Promise.all(update.map(async n => {
            // console.log(`Preview ${n}`)
            let [lower, upper] = this.getVolumeVOI(this.viewports[0])
            this.previewViewports[n].setVOI({lower, upper})
            await this.renderCineFromViewport(n, this.previewViewports[n]) 
            this.previewViewports[n].setVOI({lower, upper})
            // await this.previewViewports[n].setImageIdIndex(idx)
            // this.previewViewports[n].setVOI()
        }))
    }
    async switchSeries(series_uid, case_id) {
        this.chart.renderGraph_()
        await this.setVolumeBySeries(series_uid);
        await new Promise((resolve) => {
            this.volume.load( (e) => { console.log("Volume finished loading",e); resolve() });
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
    getAllAnnotations(viewport) {
        return ["GravisROI","Probe"].flatMap(
            type => cornerstone.tools.annotation.state.getAnnotations((viewport || this.viewports[0]).element,type) || []
        );
    }
    async updateChart() {
        if (! this.volume.imageData ) {
            return;
        }
        let annotations = this.getAllAnnotations();
        if (! annotations ) {
            if (this.chart.file_.length > 0 )
                this.chart.updateOptions( {file: [] });
            return;
        }
        var data = []
        var labels = ["time",]
        
        var seriesOptions = {}
        for (var annotation of annotations){
            data.push( {
                normal: annotation.metadata.viewPlaneNormal,
                view_up: annotation.metadata.viewUp,
                bounds: this.volume.imageData.getBounds(),
                handles: annotation.data.handles.points,
                handles_indexes: annotation.data.handles.points.map( pt=>cornerstone.utilities.transformWorldToIndex(this.volume.imageData, pt)),
                tool: annotation.metadata.toolName
            })
            labels.push(annotation.data.label)
            seriesOptions[annotation.data.label] = { color: annotation.chartColor }
        }

        try {
            const timeseries = await doFetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/timeseries`,
                 {annotations: data, chart_options: this.chart_options})
            const options = { 'file':  timeseries["data"], labels: labels, series: seriesOptions} 
            this.chart.updateOptions( options );
        } catch (e) {
            console.warn(e)
            return
        }
    }
    // async setGraspVolume(seriesInfo) {
    //     await this.setVolumeByImageIds(seriesInfo.imageIds,seriesInfo.series_uid)
    // }
    addAnnotationToViewport(tool_name,viewport_n) {
        var viewport = this.viewports[viewport_n]
        var cam = viewport.getCamera()
        var idx = Math.max(0,...Object.values(this.annotations).map(a => a.idx+1));

        var center_point = viewport.worldToCanvas(cam.focalPoint)
        if (tool_name == "GravisROI" )
            var points = [
                [ center_point[0], center_point[1]-50 ], // top
                [ center_point[0], center_point[1]+50 ], // bottom
                [ center_point[0]-50, center_point[1] ], // left
                [ center_point[0]+50, center_point[1] ], // right
            ].map(viewport.canvasToWorld)
        else if ( tool_name == "Probe") {
            var points = [viewport.canvasToWorld(center_point)];
        } else {
            throw Error("Unknown annotation type.")
        }
        var new_a = {
            chartColor: `rgb(${HSLToRGB(idx*(360/1.618033988),50,50).join(",")})`,
            highlighted: true,
            invalidated: false,
            isLocked: false,
            isVisible: true,
            annotationUID: cornerstone.utilities.uuidv4(),
            metadata: {
                idx: idx,
                viewportId: this.viewportIds[viewport_n],
                cam: viewport.getCamera(),
                toolName: tool_name,
                viewPlaneNormal: cam.viewPlaneNormal,
                viewUp: cam.viewUp,
                FrameOfReferenceUID: viewport.getFrameOfReferenceUID()
            },
            data: {
                cachedStats: {},
                label: `Annotation ${idx+1}`,
                handles: {
                    textBox:{"hasMoved":false,"worldPosition":[0,0,0],"worldBoundingBox":{"topLeft":[0,0,0],"topRight":[0,0,0],"bottomLeft":[0,0,0],"bottomRight":[0,0,0]}},
                    points: points,
                    activeHandleIndex:null
                },
            },
        }
        cornerstone.tools.annotation.state.addAnnotation(viewport.element,new_a)
        cornerstone.tools.utilities.triggerAnnotationRenderForViewportIds(this.renderingEngine,[this.viewportIds[viewport_n]]) 
        this.annotations[new_a.annotationUID] = { uid: new_a.annotationUID, label: new_a.data.label, ...new_a.metadata }
    }
    async deleteAnnotation(annotation_info) {
        const viewport = this.viewports.find((x)=>x.id == annotation_info.viewportId);
        cornerstone.tools.annotation.state.removeAnnotation(annotation_info.uid, viewport.element)
        cornerstone.tools.utilities.triggerAnnotationRenderForViewportIds(this.renderingEngine,[annotation_info.viewportId]) 
        await this.updateChart()
    }
    goToAnnotation(annotation_info) {
        const viewport = this.viewports.find((x)=>x.id == annotation_info.viewportId);
        viewport.setCamera(annotation_info.cam);
        this.renderingEngine.renderViewports([annotation_info.viewportId]);
    }
    initChart() {
        var g = new Dygraph(document.getElementById("chart"), [],
        {
            // legend: 'always',
            // valueRange: [0.0, 1000],
            gridLineColor: 'white',
            hideOverlayOnMouseOut: false,
            labels: ['seconds', 'Random'],
            axes: {
                x: {
                    axisLabelFormatter: function(x) {
                        if (parseFloat(x))
                          return `${parseFloat(x)}s`;
                        return ''
                    }
                  }
            },
            underlayCallback: (function(canvas, area, g) {
                if (! this.study_uid ) {
                    return
                }
                var bottom_left = g.toDomCoords(this.selected_time, -20);  
                var left = bottom_left[0];
                canvas.fillStyle = "rgba(255, 255, 102, 1.0)";
                canvas.fillRect(left-2, area.y, 4, area.h);
              }).bind(this),
              pointClickCallback: function(event, p) {

             }
    
            },
            
        );
        return g;
    }
    async renderCineFromViewport(n, dest_viewport=null) {
        var viewport = this.viewports[n];
        var cam = viewport.getCamera()
    
        const volumeId = viewport.getActors()[0].uid;
        var volume = cornerstone.cache.getVolume(volumeId)
        var index = cornerstone.utilities.transformWorldToIndex(volume.imageData, cam.focalPoint)
        console.log(`Current view index: ${index}`);
        if (cam.viewPlaneNormal[0] == 1) {
            var view = "SAG"
            var val = index[2]
        } else if  (Math.abs(cam.viewPlaneNormal[1]) == 1) {
            var view = "COR"
            var val = index[0]
        } else {
            var view = "AX"
            var val = index[1]
        }
        var info = await (
                await fetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/processed_results/CINE/${view}?slice_location=${val}`, {
            method: 'GET',   credentials: 'same-origin'
        })).json() 
        // console.log("Preview info:", info)
        var urls = info.urls
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
        let [lower, upper] = this.getVolumeVOI(viewport);
        dest_viewport.setVOI({lower, upper})
        await dest_viewport.setStack(urls,dest_viewport.currentImageIdIndex);
        // console.log(cornerstone.requestPoolManager.getRequestPool().interaction)

        // cornerstone.tools.utilities.stackPrefetch.enable(dest_viewport.element);
    }
    
}



// var toolsAlreadyActive = false;


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
    let start_result = await startJob(type, case_, params);
    console.log(`Do Job`,start_result.id);
    for (let i=0;i<100;i++) {
        let result = await getJob(type,start_result.id)
        if ( result["status"] == "Success" ) {
            return result;
        }
        await sleep(100);
    }
    return;
}

async function doFetch(url, body) {
    let raw_result = await fetch(url, {
        method: 'POST', 
        credentials: 'same-origin',        
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify(body),
    })
    let text = await raw_result.text();
    
    try {
        return JSON.parse(text)
    } catch (e) {
        console.warn(text);
        throw e
    }
}
async function startJob(type, case_, params) {
    var body = {
        case: case_,
        parameters: params,
    };
    var raw_result = await fetch(`/job/${type}`, {
        method: 'POST', 
        credentials: 'same-origin',        
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify(body),
    })
    try {
        return await raw_result.json()
    } catch (e) {
        console.warn(raw_result)
        throw e
    }
    
}

async function getJob(job, id) {
    var result = await (await fetch(`/job/${job}?id=${id}`, {
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
    window.addEventListener( "error", ( error ) => {
        alert(`Unexpected error! \n\n ${error.message}`)
    })
}


function HSLToRGB (h, s, l) {
    s /= 100;
    l /= 100;
    const k = n => (n + h / 30) % 12;
    const a = s * Math.min(l, 1 - l);
    const f = n =>
      l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
    return [255 * f(0), 255 * f(8), 255 * f(4)];
  };

export { GraspViewer, doJob };