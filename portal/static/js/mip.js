import { confirmPrompt, scrollViewportToPoint, doFetch, errorPrompt, errorToast, debounce, loadVolumeWithRetry, Vector, fixUpCrosshairs, viewportInVolume } from "./utils.js";
const transferFunction = ({lower, upper}) => {
    const cfun = vtk.Rendering.Core.vtkColorTransferFunction.newInstance();
    const presetToUse = vtk.Rendering.Core.vtkColorTransferFunction.vtkColorMaps.getPresetByName("Rainbow Blended Black");
    cfun.applyColorMap(presetToUse);
    cfun.setMappingRange(lower, upper);
    return cfun;
}


class AuxManager {
    type = "generic";
    viewer;
    viewport;
    mip_details;
    previewing = false; 
    is_switching = false;
    ori_dicom_set;
    current_set_type;
    volume; 
    synced_viewport = null;
    current_stats = null;
    _no_sync = false;
    constructor( viewer ) {
        this.viewer = viewer;
        this.previewing = false;
        this.ori_dicom_set = this.viewer.studies_data.volumes.find(x=>x.type=="ORI").dicom_set;
        this.auxScroll = this.auxScroll.bind(this)
        
        this.stackMainScroll = this.stackMainScroll.bind(this)
        this.volumeMainScroll = this.volumeMainScroll.bind(this)
    }

    async init(graspVolumeInfo, selected_index) {
        if (this.current_set_type) {
            await this.selectStack(this.current_set_type);
        }
    }
    async switch(index, preview, targetImageIdIndex=null) {}
    async startPreview(idx) {}
    async setPreview(idx) {}
    async stopPreview() {}

    getStats() {
        const annotations = this.viewer.annotation_manager.getAllAnnotations(this.viewport)
        const stats = annotations.map(a=>{return {label: a.data.label, stats:a.data.cachedStats[`volumeId:cornerstoneStreamingImageVolume:${this.current_set_type}_AUXVOLUME`]}})
        return stats;
    }
    installEventHandlers() {
        // Install the basic event handlers
        const el = this.viewport.element;
        el.ondblclick = e => {
            //const el = auxViewport.element;
            const el = document.getElementById("aux-container-outer");
            if (el.getAttribute("fullscreen") != "true") {
                el.setAttribute("fullscreen", "true");
                el.style.gridArea = "e / e / f / f";
                el.style.zIndex = 1;
            } else {
                el.removeAttribute("fullscreen");
                el.style.gridArea = "d";
                el.style.zIndex = 0;
            }
            this.viewer.renderingEngine.resize(true, true);
        }
        el.oncontextmenu = e=>e.preventDefault();
    }
    auxScroll(evt) {   
        // Event handler for scrolling the aux viewport. 
        if (!this.synced_viewport) return;
        if (this._no_sync) return;
        // Scroll the synced viewport to the same slice as the aux viewport.
        this.synced_viewport.suppressEvents = true;
        scrollViewportToPoint(this.synced_viewport, this.viewport.getCamera().focalPoint, false)      
        this.synced_viewport.suppressEvents = false;

    }
    cycleCamera() {
        // Swap the aux view between sagittal, coronal, axial views.
        const vals = []
        var this_MPR = 0;
        let n = 0;
        for (var [k,v] of Object.entries(cornerstone.CONSTANTS.MPR_CAMERA_VALUES)) {
            vals.push([k,v]);
            if (k == this.current_MPR) {
                this_MPR = n;
            }
            n++;
        }
        var next_MPR = (this_MPR+1) % vals.length;
        this.viewport.setCameraNoEvent(vals[next_MPR][1]);
        this.viewport.resetCameraNoEvent();
        this.setSyncedViewport();
        if (this.synced_viewport)
            this.volumeMainScroll({target:this.synced_viewport.element, explicitOriginalTarget:this.synced_viewport.element})
        this.viewport.render();
        this.current_MPR = vals[next_MPR][0];
    }
    stackMainScroll(evt) {
        // Event handler on the main viewports when the aux viewer is a StackViewport
        if (!this.synced_viewport || this._no_sync) return;
        const vp = this.viewer.viewports.find(v=>v.element==evt.target);
        if (vp != this.synced_viewport) return;
        if (this.viewport.getImageIds().length == 0) return;
        if (this.viewer.rotate_mode) return;
        this.viewport.suppressEvents = true;
        this.viewport.setImageIdIndex(vp.getCurrentImageIdIndex());
        this.viewport.suppressEvents = false;
        this.viewport.targetImageIdIndex = this.viewport.getCurrentImageIdIndex();
    }
    
    volumeMainScroll(evt) {
        // Event handler on the main viewports when the aux viewer is a VolumeViewport
        if (!this.synced_viewport || this._no_sync || !this.viewport.getDefaultActor()) return;
        const vp = this.viewer.viewports.find(v=>v.element==evt.target);
        if (vp != this.synced_viewport || !viewportInVolume(vp)) return;
        // True if the event came from scrolling, false if from manually moving crosshairs in a different viewport
        // Only might need to fix this on scroll; if I'm manually moving the crosshairs things are fine.
        const needsFixCrosshairs = evt.explicitOriginalTarget == evt.target; 
        
        if (this.viewer.rotate_mode) {
            const pan = this.viewport.getPan();
            const zoom = this.viewport.getZoom();
            this.viewport.setCameraNoEvent(vp.getCamera());
            this.viewport.suppressEvents = true;
            try {
                this.viewport.setZoom(zoom);
                this.viewport.setPan(pan);
            } finally {
                this.viewport.suppressEvents = false;
            }   
            this.viewport.render();
        } else {
            scrollViewportToPoint(this.viewport,vp.getCamera().focalPoint, true, needsFixCrosshairs)
        }

        // scrollViewportToPoint(this.viewport,vp.getCamera().focalPoint, true); 
    }
    endRotateMode() {
        if (this.synced_viewport) {
            const pan = this.viewport.getPan();
            const zoom = this.viewport.getZoom();
            this.viewport.setCameraNoEvent(this.synced_viewport.getCamera());
            this.viewport.suppressEvents = true;
            try {
                this.viewport.setZoom(zoom);
                this.viewport.setPan(pan);
            } finally {
                this.viewport.suppressEvents = false;
            }   
            this.viewport.render();
        }
    }

    async createViewport(){
        await this.switchViewportType()
        this.installEventHandlers()

        cornerstone.eventTarget.addEventListener(cornerstone.tools.Enums.Events.ANNOTATION_MODIFIED,debounce(250, async (evt) => {
            await this.updateAnnotationStats()
        }));
    }

    async updateAnnotationStats() {
        // this.viewer.annotation_manager.updateChart();
        const annotations = this.viewer.annotation_manager.getAllAnnotations(this.viewport);
        const data = this.viewer.annotation_manager.getAnnotationsQuery(annotations).data;
        if (!this.current_set_id) { 
            return
        }
        let updating_event = new CustomEvent("stats-updating", {});
        window.dispatchEvent(updating_event);        
        const results = await doFetch(`/api/case/${this.viewer.case_id}/dicom_set/${this.current_set_id}/volume_stats`,{"annotations":data, "frame_of_reference": this.viewport.getFrameOfReferenceUID()});
        // console.log(results)
        let event = new CustomEvent("stats-update", {
            detail: results
        });
        this.current_stats = results;
        window.dispatchEvent(event);
    }
    async switchViewportType(type) {
        var orient = null;
        if (type != "stack") {
            orient = cornerstone.CONSTANTS.MPR_CAMERA_VALUES.axial
        }
        const viewInput = this.viewer.genViewportDescription("AUX", orient, document.getElementById("aux-container"), "VIEW")
        if (this.viewport) {
            this.removeCameraSyncHandlers(this.viewport.element);
        }
        this.viewer.renderingEngine.enableElement(viewInput)
        this.viewport = this.viewer.renderingEngine.getViewport(viewInput.viewportId);
        if (type == "stack" && this.viewer.case_data.case_type.indexOf("Onco") != -1) {
            this.viewport.setProperties( { "RGBTransferFunction": transferFunction})
        }
        this.addCameraSyncHandlers(this.viewport.element);
        const tool_group = cornerstone.tools.ToolGroupManager.getToolGroup(`STACK_TOOL_GROUP_AUX`);
        if (tool_group) {
            tool_group.addViewport(this.viewport.id, this.viewer.renderingEngine.id);
        }
    }
    removeCameraSyncHandlers(el) {
        if (this.viewport.type != 'stack') {
            el.removeEventListener("CORNERSTONE_CAMERA_MODIFIED",this.auxScroll);
            for (const vp of this.viewer.viewports.slice(0,3)) {
                vp.element.removeEventListener("CORNERSTONE_CAMERA_MODIFIED", this.volumeMainScroll)
            }
        } else {
            el.removeEventListener("CORNERSTONE_STACK_VIEWPORT_SCROLL",this.auxScroll);
            for (const vp of this.viewer.viewports.slice(0,3)) {
                vp.element.removeEventListener("CORNERSTONE_CAMERA_MODIFIED", this.stackMainScroll)
            }
        }
    }
    addCameraSyncHandlers(el) {
        if (this.viewport.type == 'stack' && this.viewer.case_data.case_type.indexOf("Onco") != -1) {
            el.addEventListener("CORNERSTONE_STACK_VIEWPORT_SCROLL",this.auxScroll);
            for (const vp of this.viewer.viewports.slice(0,3)) {
                vp.element.addEventListener("CORNERSTONE_CAMERA_MODIFIED", this.stackMainScroll)
            }
        } else {
            el.addEventListener("CORNERSTONE_CAMERA_MODIFIED", this.auxScroll);
            for (const vp of this.viewer.viewports.slice(0,3)) {
                vp.element.addEventListener("CORNERSTONE_CAMERA_MODIFIED", this.volumeMainScroll)
            }
        }
    }
    setSyncedViewport() {
        // Work out which viewport to sync with the aux viewer.
        this.synced_viewport = null;
        if (!this.viewport.getFrameOfReferenceUID()) {
            return;
        }
        for (var viewport of this.viewer.viewports.slice(0,3)){
            if (Vector.eq(viewport.getCamera().viewPlaneNormal,this.viewport.getCamera().viewPlaneNormal) 
                && this.viewport.getFrameOfReferenceUID() == viewport.getFrameOfReferenceUID()) { // If the frame of reference doesn't match, don't sync
                    this.synced_viewport = viewport;
                    break;
            }
        }
    }
    async loadVolume(type, set_id, urls) {
        // Load a volume into the aux viewer.
        const volumeId = `cornerstoneStreamingImageVolume:${set_id}_${type}_AUXVOLUME`;
        const volume = await cornerstone.volumeLoader.createAndCacheVolume(volumeId, { imageIds:urls });
        volume.imageData.setDirection(volume.direction.map(Math.round))
        
        this.volume = volume;
        // Use the orientation showing the native image plane
        for (var [k,v] of Object.entries(cornerstone.CONSTANTS.MPR_CAMERA_VALUES)){
            if (this.current_MPR) {
                if (this.current_MPR == k) {
                    this.viewport.setCamera(v);
                    break;
                }
            } else if (Vector.dot(v.viewPlaneNormal,volume.imageData.getDirection().slice(-3)) != 0) {
                this.viewport.setCamera(v);
                this.current_MPR = k;
                break;
            }
        }
        await cornerstone.setVolumesForViewports( 
            this.viewer.renderingEngine,
            [{volumeId},],
            [this.viewport.id]
        );

        this.setSyncedViewport();

        const actor = this.viewport.getDefaultActor().actor;
        const [ lower, upper ] = actor.getProperty().getRGBTransferFunction(0).getRange(); // Not totally sure about this
        actor.getProperty().setRGBTransferFunction(0, transferFunction({lower, upper}));
        window.requestAnimationFrame(async() => await this.updateAnnotationStats())
        loadVolumeWithRetry(volume); // don't await, just return the volume
        
        return volume;
    }
    async loadStack(urls) {
        // Load a stack into the aux viewer. 
        // Assume it's in the native image orientation. Probably could check this with the frame of reference
        const native_vp = this.viewer.renderingEngine.getViewport(this.viewer.getNativeViewports()[0]);
        const index = native_vp.getCurrentImageIdIndex() || this.viewport.getCurrentImageIdIndex() || 0;
        await this.viewport.setStack(urls, index);
        cornerstone.tools.utilities.stackPrefetch.enable(this.viewport.element);
        
    }
    async showImages(type, set_id, urls) {
        try { // Try to treat this as a volume. If it throws, try it as a stack.
            if (this.viewport.type == "stack") {
                this.switchViewportType("volume");
            }
            return await this.loadVolume(type, set_id, urls);
        } catch (e) {
            console.warn(e);
            if (this.viewport.type != "stack") {
                this.switchViewportType("stack");
            }
            return await this.loadStack(urls);
        }
    }
    async selectStack(type) {
        this.current_set_type = type;
        const { urls, set_id } = (await doFetch(`/api/case/${this.viewer.case_id}/dicom_set/${this.ori_dicom_set}/processed_results/${type}`,null, "GET"));
        this.current_set_id = set_id;
        const [ zoom, pan ] = [this.viewport.getZoom(), this.viewport.getPan()]
        // const fp = this.synced_viewport.getCamera().focalPoint;
        // const native_vp = this.viewer.renderingEngine.getViewport(this.viewer.getNativeViewports()[0]);

        this._no_sync = true;
        try {
            await this.showImages(type,set_id, urls)
            this.viewport.setZoom(zoom);
            this.viewport.setPan(pan);    
        } finally {
            this._no_sync = false;
        }
        if (this.viewport.type != 'stack' && this.synced_viewport) {
            scrollViewportToPoint(this.viewport,this.synced_viewport.getCamera().focalPoint, true);
        }
        this.viewport.render();
    }
}

class MIPManager extends AuxManager{
    type = "MIP"
    current_set_type = "stack";

    installEventHandlers() {
        super.installEventHandlers()
        this.viewport.element.addEventListener("CORNERSTONE_CAMERA_MODIFIED", debounce(500, async (evt) => {                
            try {
                await this.prefetchSliceOverTime();
            } catch (e) {
                console.warn(e);
            }
        }));
    }
    async createViewport(){
        await this.switchViewportType('stack')
        this.installEventHandlers()
    }

    async selectStack(type) {
        // Do nothing; MIP manager juggles stacks itself.
    }
    addCameraSyncHandlers(el) {
        // Do nothing; do not sync with main viewports
    }
    async updateAnnotationStats() {
        // do nothing
    }
    async init(graspVolumeInfo, selected_index) {
        // console.log("mip init", graspVolumeInfo, selected_index)
        // Get MIP metadata info, currently only need slice_locations
        const current_info = graspVolumeInfo[selected_index];
        try {
            this.mip_details = (await doFetch(`/api/case/${this.viewer.case_id}/dicom_set/${this.ori_dicom_set}/mip_metadata?acquisition_number=${current_info.acquisition_number}`,null, "GET")).details;
            // console.log("mip details", this.mip_details)
            // Set Initial MIP Image         
            await this.switch(selected_index, false);
            await this.setPreview(selected_index);
        } catch (e) {
            console.warn(e); 
        }
    }
    async switch(index, preview, targetImageIdIndex=null) {
        // console.log("switch", index, preview, targetImageIdIndex)
        this.is_switching = true;
        try {
            const current_info = this.viewer.current_study[index];
            const viewport = this.viewport;
            const cam = viewport.getCamera();
            const slice_location = this.mip_details[viewport.targetImageIdIndex]["slice_location"];

            let mip_urls = {}
            // In the preview mode need to get all time points for the given angle (slice_location)
            // In the regular, not preview mode, need to get all angles (slice_locations) for the given time point
            const query = ( preview? `slice_location=${slice_location}`: `acquisition_number=${current_info.acquisition_number}`)

            mip_urls = (await doFetch(`/api/case/${this.viewer.case_id}/dicom_set/${this.ori_dicom_set}/processed_results/MIP?`+ query,null, "GET")).urls;
            // console.log("mip_urls", mip_urls);
            if ( mip_urls.length > 0 ) {
                await viewport.setStack(mip_urls, targetImageIdIndex || viewport.targetImageIdIndex);
                cornerstone.tools.utilities.stackPrefetch.enable(viewport.element);
                if (!cam.focalPoint.every( k => k==0 )) viewport.setCamera(cam);
                viewport.render();
            }
        } finally {
            this.is_switching = false;
        }
    }

    async prefetchSliceOverTime() {
        // console.log("cache")
        const viewport = this.viewport;
        
        let slice_location = 0.0;
        try {
            slice_location = this.mip_details[viewport.targetImageIdIndex]["slice_location"]; 
        } catch (e) {
            // console.log("mip_details is not initialized yet. setting slice_location to 0.0.")
        }
        let imageIdsToPrefetch = (await doFetch(`/api/case/${this.viewer.case_id}/dicom_set/${this.ori_dicom_set}/processed_results/MIP?slice_location=${slice_location}`,null, "GET")).urls;
        
        const requestFn = (imageId, options) => cornerstone.imageLoader.loadAndCacheImage(imageId, options);
        const priority = 0;
        const requestType = cornerstone.Enums.RequestType.Prefetch;
        imageIdsToPrefetch.forEach((imageId) => {
            // IMPORTANT: Request type should be passed if not the 'interaction'
            // highest priority will be used for the request type in the imageRetrievalPool
            const options = {
              targetBuffer: {
                type: 'Float32Array',
                offset: null,
                length: null,
              },
              requestType,
            };
        
            cornerstone.imageLoadPoolManager.addRequest(
              requestFn.bind(null, imageId, options),
              requestType,
              // Additional details
              {
                imageId,
              },
              priority
              // addToBeginning
            );
        });
    }

    async startPreview(idx) {
        if (this.previewing) {
            return;
        }
        console.log("startPreview", idx)
        this.previewing = true;
        // Resetting MIP image stack with images at the last saved angle for all time points
        try {
            await this.switch(idx, true);
        } catch (e) {
            console.warn(e);
        }
    }

    async setPreview(idx) {
        if (this.is_switching) {
            return;
        }
        // console.log("setPreview",idx)

        try {
            // Update MIP Viewport
            const vp = this.viewport;
            await vp.setImageIdIndex(idx);

            // The idea here is to try and force it to automatically recalculate the VOI.
            // vp.stackInvalidated = true;
            // vp._resetProperties();
            // await vp.setImageIdIndex(idx);
            // if (vp.voiRange.lower == vp.voiRange.upper) {
                // vp.setVOI({lower:vp.voiRange.lower, upper: vp.voiRange.lower+1});
            // }

            // const imageMetadata = vp._getImageDataMetadata(vp.csImage);
            // console.warn(imageMetadata.imagePixelModule);
            // let { windowCenter, windowWidth } = imageMetadata.imagePixelModule;
            // let voiRange = typeof windowCenter === 'number' && typeof windowWidth === 'number'
            //     ? cornerstone.utilities.windowLevel.toLowHighRange(windowWidth, windowCenter)
            //     : undefined;
            // console.warn(voiRange);
            // if (voiRange.lower == voiRange.upper) {
            //     vp.setVOI({lower:voiRange.lower, upper: voiRange.lower+1});
            // } else {
            //     vp.setVOI(voiRange);
            // }
            vp.render();
        } catch (e) {
            console.warn(e);
        }
    }

    async stopPreview(idx) {
        console.log("stopPreview", idx)
        // Resetting MIP image stack with images at a given time point with all available angles.
        try {
            this.previewing = false;
            const vp = this.viewport;
            const voi = vp.voiRange;
            await this.switch(idx, false);
            vp.setVOI(voi);
            console.log(JSON.stringify(vp.voiRange));

        } catch (e) {
            console.warn(e);
        }
    }
}
export { MIPManager, AuxManager }