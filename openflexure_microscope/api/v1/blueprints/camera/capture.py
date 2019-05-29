from openflexure_microscope.api.utilities import get_bool, JsonPayload
from openflexure_microscope.api.v1.views import MicroscopeView
from openflexure_microscope.utilities import filter_dict

from flask import Response, jsonify, request, abort, url_for, redirect, send_file


class ListAPI(MicroscopeView):

    def get(self):
        """
        Get list of image captures.

        .. :quickref: Captures; Get collection of captures

        :>header Accept: application/json
        :query include_unavailable: return json representations of captures that have been completely deleted

        :>jsonarr boolean available: availability of capture data
        :>jsonarr string filename: filename of capture
        :>jsonarr string id: unique id of the capture object
        :>jsonarr boolean keep_on_disk: keep the capture file on microscope after closing
        :>jsonarr boolean locked: file locked for modifications (mostly used for video recording)
        :>jsonarr string path: path on pi storage to the capture file, if available
        :>jsonarr boolean stream: capture stored in-memory as a BytesIO stream
        :>jsonarr json uri: - **download** *(string)*: api uri to the capture file download
                            - **state** *(string)*: api uri to the capture json representation

        :>header Content-Type: application/json
        :status 200: capture found
        :status 404: no capture found with that id
        """
        include_unavailable = get_bool(request.args.get('include_unavailable'))

        if include_unavailable:
            captures = [image.state for image in self.microscope.camera.images]
        else:
            captures = [image.state for image in self.microscope.camera.images if image.state['available']]

        return jsonify(captures)

    def delete(self):
        """
        Delete all captures (not yet implemented)

        .. :quickref: Captures; Delete all captures
        """
        for image in self.microscope.camera.images:
            image.delete()

        captures = [image.state for image in self.microscope.camera.images]

        return jsonify(captures)

    def post(self):
        """
        Create a new image capture.

        .. :quickref: Captures; New capture

        **Example request**:

        .. sourcecode:: http

          POST /camera/capture HTTP/1.1
          Accept: application/json

          {
            "filename": "myfirstcapture", 
            "temporary": false, 
            "use_video_port": true,
            "bayer": true,
            "size": {
                "width": 640,
                "height": 480
            }
          }

        :>header Accept: application/json

        :<json string filename: filename of stored capture
        :<json boolean temporary: delete the capture file on microscope after closing
        :<json boolean use_video_port: capture still image from the video port
        :<json boolean bayer: keep raw capture data in the image file
        :<json json size:   - **x** *(int)*: x-axis resize
                            - **y** *(int)*: y-axis resize

        :>json boolean available: availability of capture data
        :>json string filename: filename of capture
        :>json string id: unique id of the capture object
        :>json boolean temporary: delete the capture file on microscope after closing
        :>json boolean locked: file locked for modifications (mostly used for video recording)
        :>json string path: path on pi storage to the capture file, if available
        :>json boolean stream: capture stored in-memory as a BytesIO stream
        :>json json uri: - **download** *(string)*: api uri to the capture file download
                         - **state** *(string)*: api uri to the capture json representation

        :<header Content-Type: application/json
        :status 200: capture created
        """
        payload = JsonPayload(request)

        filename = payload.param('filename')
        temporary = payload.param('temporary', default=False, convert=bool)
        use_video_port = payload.param('use_video_port', default=False, convert=bool)
        bayer = payload.param('bayer', default=True, convert=bool)
        metadata = payload.param('metadata', default={}, convert=dict)
        tags = payload.param('tags', default=[], convert=list)

        resize = payload.param('size', default=None)
        if resize:
            if ('width' in resize) and ('height' in resize):
                resize = (int(resize['width']), int(resize['height']))  # Convert dict to tuple
            else:
                abort(404)

        # Explicitally acquire lock (prevents empty files being created if lock is unavailable)
        with self.microscope.camera.lock:
            output = self.microscope.camera.new_image(
                write_to_file=True,
                temporary=temporary,
                filename=filename)

            self.microscope.camera.capture(
                output,
                use_video_port=use_video_port,
                resize=resize,
                bayer=bayer)

            metadata.update({'Position': self.microscope.state['stage']['position']})

            output.put_metadata(metadata)
            output.put_tags(tags)

        return jsonify(output.state)


class CaptureAPI(MicroscopeView):

    def get(self, capture_id):
        """
        Get JSON representation of a capture

        .. :quickref: Capture; Get capture

        **Example request**:

        .. sourcecode:: http

          GET /camera/capture/d0b2067abbb946f19351e075c5e7cd5b/ HTTP/1.1
          Accept: application/json

        **Example response**:

        .. sourcecode:: http

          HTTP/1.1 200 OK
          Vary: Accept
          Content-Type: application/json

          {
              "available": true, 
              "bytestream": false, 
              "keep_on_disk": false, 
              "locked": false, 
              "metadata": {
                  "filename": "2018-11-16_10-21-53.jpeg", 
                  "id": "d0b2067abbb946f19351e075c5e7cd5b", 
                  "path": "capture/2018-11-16_10-21-53.jpeg", 
                  "time": "2018-11-16_10-21-53"
              }
              "uri": {
                  "download": "/api/v1/capture/d0b2067abbb946f19351e075c5e7cd5b/download", 
                  "state": "/api/v1/capture/d0b2067abbb946f19351e075c5e7cd5b/"
              }
          }

        :>json boolean available: availability of capture data
        :>json string filename: filename of capture
        :>json string id: unique id of the capture object
        :>json boolean keep_on_disk: keep the capture file on microscope after closing
        :>json boolean locked: file locked for modifications (mostly used for video recording)
        :>json string path: path on pi storage to the capture file, if available
        :>json boolean stream: capture stored in-memory as a BytesIO stream
        :>json json uri: - **download** *(string)*: api uri to the capture file download
                         - **state** *(string)*: api uri to the capture json representation

        """
        capture_obj = self.microscope.camera.image_from_id(capture_id)

        if not capture_obj:
            return abort(404)  # 404 Not Found

        # Get capture state
        capture_metadata = capture_obj.state

        # Add API routes to returned state
        uri_dict = {
            'uri': {'state': '{}'.format(url_for('.capture', capture_id=capture_obj.id))}
        }

        # If available, also add download link
        if capture_metadata['available']:
            uri_dict['uri']['download'] = '{}download/{}'.format(
                url_for('.capture', capture_id=capture_obj.id),
                capture_obj.filename
            )

        capture_metadata.update(uri_dict)

        return jsonify(capture_metadata)

    def delete(self, capture_id):
        """
        Delete all capture data from the Pi, even if `keep_on_disk=true;`.

        .. :quickref: Capture; Delete capture.
        """
        capture_obj = self.microscope.camera.image_from_id(capture_id)

        if not capture_obj:
            return abort(404)  # 404 Not Found

        capture_obj.delete()

        return jsonify({"return": capture_id})

    def put(self, capture_id):
        """
        Add arbitrary metadata to the capture (stored in an accompanying capture `.yaml` file)

        .. :quickref: Capture; Update capture metadata

        **Example request**:

        .. sourcecode:: http

          PUT /camera/capture/d0b2067abbb946f19351e075c5e7cd5b HTTP/1.1
          Accept: application/json

          {
            "user_id": "ofm_1234", 
            "patient_number": 1452, 
          }

        :>header Accept: application/json

        :<header Content-Type: application/json
        :status 200: metadata updated
        """

        capture_obj = self.microscope.camera.image_from_id(capture_id)

        if not capture_obj:
            return abort(404)  # 404 Not Found
        
        data_dict = JsonPayload(request).json

        capture_obj.put_metadata(data_dict)

        capture_metadata = capture_obj.state

        return jsonify(capture_metadata)


class DownloadRedirectAPI(MicroscopeView):
    def get(self, capture_id):
        """
        Return image data for a capture.

        Return capture data as an image file with the requested filename. 
        I.e., `/(capture_id)/download/foo.jpeg` will download the image as 
        `foo.jpeg`, regardless of the capture's initially set filename.

        Route automatically redirects to download the capture under it's currently set filename. 
        I.e., `/(capture_id)/download` will 
        redirect to `/(capture_id)/download/(filename)`.

        .. :quickref: Capture; Download capture image

        **Example request**:

        .. sourcecode:: http

          GET /camera/capture/d0b2067abbb946f19351e075c5e7cd5b/download/2018-11-20_16-04-17.jpeg HTTP/1.1
          Accept: image/jpeg

        :>header Accept: image/jpeg
        :query thumbnail: return an image thumbnail e.g. ?thumbnail=true

        :>header Content-Type: image/jpeg
        :status 200: capture data found
        :status 404: no capture found with that id

        """
        capture_obj = self.microscope.camera.image_from_id(capture_id)

        if not capture_obj or not capture_obj.state['available']:
            return abort(404)  # 404 Not Found

        thumbnail = get_bool(request.args.get('thumbnail'))

        return redirect(url_for(
            '.capture_download',
            capture_id=capture_id,
            filename=capture_obj.filename,
            thumbnail=thumbnail
        ), code=307)


class DownloadAPI(MicroscopeView):
    def get(self, capture_id, filename):

        capture_obj = self.microscope.camera.image_from_id(capture_id)

        if not capture_obj or not capture_obj.state['available']:
            return abort(404)  # 404 Not Found

        thumbnail = get_bool(request.args.get('thumbnail'))

        # If no filename is specified, redirect to the capture's currently set filename
        if not filename:
            return redirect(url_for(
                'capture_download',
                capture_id=capture_id,
                filename=capture_obj.filename,
                thumbnail=thumbnail
            ), code=307)

        # Download the image data using the requested filename
        if thumbnail:
            img = capture_obj.thumbnail
        else:
            img = capture_obj.data

        return send_file(
            img,
            mimetype='image/jpeg')


class MetadataRedirectAPI(MicroscopeView):
    def get(self, capture_id):
        """
        Return metadatadata for a capture.

        Return capture metadata as a YAML file with the requested filename. 
        I.e., `/(capture_id)/download/bar.yaml` will download the file as 
        `bar.yaml`, regardless of the capture's initially set filename.

        Route automatically redirects to download the capture metadata under it's currently set filename. 
        I.e., `/(capture_id)/download` will 
        redirect to `/(capture_id)/download/(filename)`.

        .. :quickref: Capture; Download capture metadata

        **Example request**:

        .. sourcecode:: http

          GET /camera/capture/d0b2067abbb946f19351e075c5e7cd5b/metadata/2018-11-20_16-04-17.yaml HTTP/1.1
          Accept: text/yaml

        :>header Accept: text/yaml
        :query as_attachment: return the image as an attachment download e.g. ?as_attachment=true

        :>header Content-Type: text/yaml
        :status 200: capture data found
        :status 404: no capture found with that id

        """
        capture_obj = self.microscope.camera.image_from_id(capture_id)

        if not capture_obj or not capture_obj.state['available']:
            return abort(404)  # 404 Not Found

        return redirect(url_for(
            '.metadata_download',
            capture_id=capture_id,
            filename=capture_obj.metadataname
        ), code=307)


class MetadataAPI(MicroscopeView):
    def get(self, capture_id, filename):

        capture_obj = self.microscope.camera.image_from_id(capture_id)

        if not capture_obj or not capture_obj.state['available']:
            return abort(404)  # 404 Not Found

        # If no filename is specified, redirect to the capture's currently set filename
        if not filename:
            return redirect(url_for(
                'capture_download',
                capture_id=capture_id,
                filename=capture_obj.metadataname
            ), code=307)

        # Download the metadata using the requested filename
        data = capture_obj.yaml

        return Response(
            data,
            mimetype="text/yaml")


class TagsAPI(MicroscopeView):
    def get(self, capture_id):
        """
        Return tag list for a capture.

        .. :quickref: Capture; Show capture tags

        **Example request**:

        .. sourcecode:: http

          GET /camera/capture/d0b2067abbb946f19351e075c5e7cd5b/tags HTTP/1.1
          Accept: text/yaml

        :>header Accept: text/yaml

        :>header Content-Type: text/yaml
        :status 200: capture data found
        :status 404: no capture found with that id
        """
        capture_obj = self.microscope.camera.image_from_id(capture_id)

        if not capture_obj or not capture_obj.state['available']:
            return abort(404)  # 404 Not Found

        metadata_tags = filter_dict(capture_obj.state, ['metadata', 'tags'])

        return jsonify(metadata_tags)
    
    def put(self, capture_id):
        """
        Add tags to the capture

        .. :quickref: Capture; Update capture tags

        **Example request**:

        .. sourcecode:: http

          PUT /camera/capture/d0b2067abbb946f19351e075c5e7cd5b/tags HTTP/1.1
          Accept: application/json

          ["tests", "mytag", "someothertag"]

        :>header Accept: application/json

        :<header Content-Type: application/json
        :status 200: metadata updated
        """

        capture_obj = self.microscope.camera.image_from_id(capture_id)

        if not capture_obj or not capture_obj.state['available']:
            return abort(404)  # 404 Not Found
        
        data_dict = JsonPayload(request).json

        if type(data_dict) != list:
            return abort(400)

        capture_obj.put_tags(data_dict)

        metadata_tags = filter_dict(capture_obj.state, ['metadata', 'tags'])

        return jsonify(metadata_tags)

    def delete(self, capture_id):
        """
        Delete tags from the capture

        .. :quickref: Capture; Delete tags.

        **Example request**:

        .. sourcecode:: http

          DELETE /camera/capture/d0b2067abbb946f19351e075c5e7cd5b/tags HTTP/1.1
          Accept: application/json

          ["tests", "mytag"]

        :>header Accept: application/json

        :<header Content-Type: application/json
        :status 200: metadata updated
        """
        capture_obj = self.microscope.camera.image_from_id(capture_id)

        if not capture_obj:
            return abort(404)  # 404 Not Found

        data_dict = JsonPayload(request).json

        if type(data_dict) != list:
            return abort(400)

        for tag in data_dict:
            capture_obj.delete_tag(str(tag))

        metadata_tags = filter_dict(capture_obj.state, ['metadata', 'tags'])

        return jsonify(metadata_tags)
