import { confirmPrompt, doFetch, errorPrompt, errorToast } from "./utils.js";

class AuxManager {
    type = "generic";
    viewer;
    viewport;
    mip_details;
    previewing = false; 
    is_switching = false;
    ori_dicom_set;

    constructor( viewer, viewport ) {
        this.viewer = viewer;
        this.viewport = viewport;
        this.previewing = false;
        this.ori_dicom_set = this.viewer.studies_data.volumes.find(x=>x.type=="ORI").dicom_set;
    }

    async init(graspVolumeInfo, selected_index) {
    }
    async switch(index, preview, targetImageIdIndex=null) {}
    async cache() {}
    async startPreview(idx) {}
    async setPreview(idx) {}
    async stopPreview() {}

    async loadVolume(type, urls) {
        const volumeId = `cornerstoneStreamingImageVolume:${type}`;
        const volume = await cornerstone.volumeLoader.createAndCacheVolume(volumeId, { imageIds:urls });
        volume.imageData.setDirection(volume.direction.map(Math.round))
        volume.load();
        await cornerstone.setVolumesForViewports( 
            this.viewer.renderingEngine,
            [{volumeId},],
            [this.viewport.id]
        );      
        this.viewport.render();
        return volume;
    }
    async loadStack(urls) {
            const native_vp = this.viewer.renderingEngine.getViewport(this.viewer.getNativeViewports()[0])
            const index = native_vp._getImageIdIndex() || this.viewer.auxViewport.getCurrentImageIdIndex() || 0
            await this.viewport.setStack(urls, index);
        this.viewport.render();
        }
    async showImages(type, urls) {
        if (this.viewport.type == "stack") {
            return await this.loadStack(urls);
        } else {
            return await this.loadVolume(type, urls);
        }
    }
    async selectStack(type) {
        const urls = (await doFetch(`/api/case/${this.viewer.case_id}/dicom_set/${this.ori_dicom_set}/processed_results/${type}`,null, "GET")).urls;
        await this.showImages(type,urls)
    }
}

class MIPManager extends AuxManager{
    type = "MIP"

    async selectStack(type) {
        // Do nothing; MIP manager juggles stacks itself.
    }

    async init(graspVolumeInfo, selected_index) {
        // Get MIP metadata info, currently only need slice_locations
        const current_info = graspVolumeInfo[selected_index];
        try {
            this.mip_details = (await doFetch(`/api/case/${this.viewer.case_id}/dicom_set/${this.ori_dicom_set}/mip_metadata?acquisition_number=${current_info.acquisition_number}`,null, "GET")).details;
            // Set Initial MIP Image         
            await this.switch(selected_index, false);
            await this.setPreview(selected_index);
        } catch (e) {
            console.warn(e); 
        }
    }
    async switch(index, preview, targetImageIdIndex=null) {
        // console.log("switch")
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

    async cache() {
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
        // console.log("startPreview")
        if (this.previewing) {
            return;
        }
        this.previewing = true;
        // Resetting MIP image stack with images at the last saved angle for all time points
        try {
            await this.switch(idx, true);
        } catch (e) {
            console.warn(e);
        }
    }

    async setPreview(idx) {
        console.log("setPreview")
        if (this.is_switching) {
            return;
        }
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
        // console.log("stopPreview")

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