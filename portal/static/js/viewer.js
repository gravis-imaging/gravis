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
        // Force cornerstone to try to use GPU rendering even if it thinks the GPU is weak.
        cornerstone.setUseCPURendering(false);
        
        await cornerstone.helpers.initDemo(); 
        // Instantiate a rendering engine
        const renderingEngineId = 'gravisRenderEngine';
        this.renderingEngine = new RenderingEngine(renderingEngineId);    

        const { ORIENTATION } = cornerstone.CONSTANTS;

        const preview_info = [["AX"],["SAG"],["COR"]]
        const [ previewViewports, previewViewportIds ] = this.createViewports("PREVIEW",preview_info, preview)

        const view_info = [["AX",ORIENTATION.AXIAL],["SAG",ORIENTATION.SAGITTAL],["COR",ORIENTATION.CORONAL],["CINE"]]
        const [ viewViewports, viewportIds ] = this.createViewports("VIEW", view_info, main)
        this.renderingEngine.setViewports([...previewViewports, ...viewViewports])

        this.viewportIds = viewportIds
        this.previewViewportIds = previewViewportIds

        this.viewports = viewportIds.map((c)=>this.renderingEngine.getViewport(c))
        this.previewViewports = previewViewportIds.map((c)=>this.renderingEngine.getViewport(c))
        // renderingEngine.enableElement(viewportInput);
        cornerstone.tools.synchronizers.createVOISynchronizer("SYNC_CAMERAS");
    
        this.createTools()
        this.renderingEngine.renderViewports([...this.viewportIds, ...this.previewViewports]);
        this.chart = this.testChart()
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
        // styles.global.color = "rgb(255,0,0)"
        styles.global.lineWidth = "1"
        cornerstone.tools.annotation.config.style.setDefaultToolStyles(styles)
        toolGroupA.addTool(StackScrollMouseWheelTool.toolName );
        toolGroupB.addTool(StackScrollMouseWheelTool.toolName );
        toolGroupA.addTool(CrosshairsTool.toolName, {
            getReferenceLineColor: (id) => { return ({"VIEW_AX": "rgb(255, 255, 100)","VIEW_SAG": "rgb(100, 100, 255)","VIEW_COR": "rgb(255, 100, 100)",})[id]},
            // getReferenceLineControllable: (id)=> true,
            // getReferenceLineDraggableRotatable: (id)=> false,
            getReferenceLineSlabThicknessControlsOn: (id)=> false,
            // filterActorUIDsToSetSlabThickness: [viewportId(4)]
          });
        
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
    
        toolGroupA.setToolPassive(CrosshairsTool.toolName, {
            // bindings: [{ mouseButton: MouseBindings.Secondary }],
        });
        
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
            toolGroup.setToolActive(window.cornerstone.tools.CrosshairsTool.toolName, {
                bindings: [{ mouseButton: window.cornerstone.tools.Enums.MouseBindings.Primary }],
            });
            // toolGroup.setToolActive(window.cornerstone.tools.WindowLevelTool.toolName, {
            //     bindings: [{ mouseButton: window.cornerstone.tools.Enums.MouseBindings.Primary }],
            // });
            toolGroup.setToolPassive(cornerstone.tools.EllipticalROITool.toolName, {
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

            const synchronizer = cornerstone.tools.SynchronizerManager.getSynchronizer("SYNC_CAMERAS");
            [...this.viewportIds.slice(0,3)].map(id => synchronizer.add({ renderingEngineId: "gravisRenderEngine", viewportId:id }))
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

    async updatePreview(n=null, idx=0) {
        console.log("Updating previews...")
        let update = [n]
        if (n==null){
            update = [0, 1, 2]
        }
        await Promise.all(update.map(async (n)=> {
            console.log(`Preview ${n}`)
            let [lower, upper] = this.viewports[0].getDefaultActor().actor.getProperty().getRGBTransferFunction(0).getRange()
            this.previewViewports[n].setVOI({lower, upper})
            await this.renderCineFromViewport(n, this.previewViewports[n]) 
            this.previewViewports[n].setVOI({lower, upper})
            // await this.previewViewports[n].setImageIdIndex(idx)
            // this.previewViewports[n].setVOI()
        }))
    }
    async switchSeries(series_uid, case_id) {
        await this.setVolumeBySeries(series_uid);
        await new Promise((resolve) => {
            this.volume.load( (e) => { console.log("Volume finished loading",e); resolve() });
        });
    }
    async switchStudy(info, case_id, keepCamera=true) {
        var [study_uid, dicom_set] = info;
        this.study_uid = study_uid;
        this.dicom_set = dicom_set;
        this.case_id = case_id
        var graspVolumeInfo = await (await fetch(`/api/case/${case_id}/dicom_set/${dicom_set}/study/${study_uid}/metadata`, {
            method: 'GET',   credentials: 'same-origin'
        })).json()
        document.getElementById("volume-picker").setAttribute("min",0)
        document.getElementById("volume-picker").setAttribute("max",graspVolumeInfo.length-1)
        document.getElementById("volume-picker").setAttribute("value",0)

        
        
        this.viewports.slice(0,3).map((v, n)=> {
            v.element.addEventListener("CORNERSTONE_CAMERA_MODIFIED", debounce(250, async (evt) => {
                // console.log(v.getCamera().position)
                try {
                    await this.updatePreview(n)
                } catch (e) {
                    console.error(e);
                }
            //    console.log({position: evt.detail.camera.position, focalPoint:evt.detail.camera.focalPoint, viewPlaneNormal: evt.detail.camera.viewPlaneNormal} );
            }));
            
            v.element.addEventListener("CORNERSTONE_TOOLS_ANNOTATION_RENDERED", debounce(100, (evt) => this.updateChart(v)));
        });
                
        await this.setVolumeBySeries(graspVolumeInfo[0]["series_uid"]),
        this.volume.load(()=>{ console.log("Volume loaded")})
        try {
            await this.updatePreview()
        } catch (e) {
            console.error(e);
        }

        console.log("Study switched");
        return graspVolumeInfo
    }
    async updateChart(v) {
        let annotations = cornerstone.tools.annotation.state.getAnnotations(v.element,"EllipticalROI");
        if (! annotations ) {
            this.chart.updateOptions( {file: [] });
            return;
        }
                let sliceIndex  = cornerstone.utilities.getImageSliceDataForVolumeViewport(v).imageIndex
                var data = []
                var labels = ["time",]
        
        var seriesOptions = {}
                for (var annotation of annotations){
                    data.push( {
                        normal: annotation.metadata.viewPlaneNormal,
                        view_up: annotation.metadata.viewUp,
                        bounds: this.volume.imageData.getBounds(),
                        ellipse: annotation.data.handles.points ////.map((x)=>cornerstone.utilities.transformWorldToIndex(this.volume.imageData, x))})
                    })
            labels.push(annotation.data.label)
            seriesOptions[annotation.data.label] = { color: annotation.chartColor }
            // console.log(annotation);
                }
        
                try {
                    const timeseries = await doFetch("/api/case/1/dicom_set/1/timeseries", {annotations: data})
            const options = { 'file':  timeseries["data"], labels: labels, series: seriesOptions} 
            this.chart.updateOptions( options );
            console.log(options)
        } catch (e) {
            console.warn(e)
                    return
                }
    }
    // async setGraspVolume(seriesInfo) {
    //     await this.setVolumeByImageIds(seriesInfo.imageIds,seriesInfo.series_uid)
    // }
    addAnnotationToViewport(viewport_n, idx) {
        var viewport = this.viewports[viewport_n]
        var cam = viewport.getCamera()

        var center_point = viewport.worldToCanvas(cam.focalPoint)
        var points = [
            [ center_point[0], center_point[1]-50 ], // top
            [ center_point[0], center_point[1]+50 ], // bottom
            [ center_point[0]-50, center_point[1] ], // left
            [ center_point[0]+50, center_point[1] ], // right
        ].map(viewport.canvasToWorld)

        var template = {
            chartColor: `rgb(${HSLToRGB(idx*(360/1.618033988),50,50).join(",")})`,
            highlighted:true,
            invalidated:false,
            isLocked: false,
            isVisible: true,
            annotationUID: cornerstone.utilities.uuidv4(),
            metadata: {
                toolName:"EllipticalROI","viewPlaneNormal":cam.viewPlaneNormal,"viewUp":cam.viewUp,"FrameOfReferenceUID":viewport.getFrameOfReferenceUID()
            },
            data: {
                cachedStats:{},
                label:`Annotation ${idx}`,
                handles: {
                    textBox:{"hasMoved":false,"worldPosition":[0,0,0],"worldBoundingBox":{"topLeft":[0,0,0],"topRight":[0,0,0],"bottomLeft":[0,0,0],"bottomRight":[0,0,0]}},
                    points: points,
                    activeHandleIndex:null
                },
            },
        }
        cornerstone.tools.annotation.state.addAnnotation(viewport.element,template)
        cornerstone.tools.utilities.triggerAnnotationRenderForViewportIds(this.renderingEngine,[this.viewportIds[viewport_n]]) 
        return { uid: template.annotationUID, label: template.data.label, viewport: viewport, idx: idx, cam: viewport.getCamera() }
    }
    async deleteAnnotation(annotation_info) {
        cornerstone.tools.annotation.state.removeAnnotation(annotation_info.uid, annotation_info.viewport.element)
        cornerstone.tools.utilities.triggerAnnotationRenderForViewportIds(this.renderingEngine,[annotation_info.viewport.id]) 
        await this.updateChart(annotation_info.viewport)        
        // let labels = this.chart.getLabels()
        // let idx = labels.findIndex((a) => a === annotation_info.label)
        // let data = this.chart.rawData_.slice()
        // data.splice(idx,idx+1)
        // labels.splice(idx,idx+1)

        // this.chart.updateOptions( { file:  data, labels: labels} );
    }
    goToAnnotation(annotation_info) {
        annotation_info.viewport.setCamera(annotation_info.cam);
        this.renderingEngine.renderViewports([annotation_info.viewport.id]);
    }
    testChart() {
        var g = new Dygraph(document.getElementById("chart"), [],
        {
            legend: 'always',
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
            }
            });
        return g;
    }
    async renderCineFromViewport(n, dest_viewport=null) {
        var viewport = this.viewports[n];
        var cam = viewport.getCamera()
    
        const volumeId = viewport.getActors()[0].uid;
        var volume = cornerstone.cache.getVolume(volumeId)
        var index = cornerstone.utilities.transformWorldToIndex(volume.imageData, cam.focalPoint)

        if (cam.viewPlaneNormal[0] == 1) {
            var view = "SAG"
            var val = index[2]
        } else if  (cam.viewPlaneNormal[1] == 1) {
            var view = "COR"
            var val = index[0]
        } else {
            var view = "AX"
            var val = index[1]
        }
        var info = await (
                await fetch(`/api/case/${this.case_id}/dicom_set/${this.dicom_set}/processed_results/CINE/${view}?series_number=${val}`, {
            method: 'GET',   credentials: 'same-origin'
        })).json() 
        console.log("Preview info:", info)
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

async function doFetch(url, body) {
    var raw_result = await fetch(url, {
        method: 'POST', 
        credentials: 'same-origin',        
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify(body),
    })
    text = await raw_result.text();
    
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