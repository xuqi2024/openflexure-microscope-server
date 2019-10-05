from openflexure_microscope.api.v1.views import MicroscopeView
from flask import jsonify, abort, Blueprint


class TaskListAPI(MicroscopeView):
    def get(self):
        """
        Get list of long-running tasks.

        .. :quickref: Tasks; Get collection of tasks

        **Example response**:

        .. sourcecode:: http

          HTTP/1.1 200 OK
          Vary: Accept
          Content-Type: application/json

          [
            {
                "end_time": "2019-01-23 16-33-33", 
                "id": "db13a66787e1419bb06b1504e4d80b0c", 
                "return": [
                0.848622546386467, 
                0.6106785018091292, 
                ], 
                "start_time": "2019-01-23 16-33-13", 
                "status": "success"
            }, 
            {
                "end_time": null, 
                "id": "df46558cc8844924821bd0181881871e", 
                "return": null, 
                "start_time": "2019-01-23 16-34-54", 
                "status": "running"
            }
          ]

        :>header Accept: application/json
        :query include_unavailable: return json representations of captures that have been completely deleted

        :>header Content-Type: application/json
        """

        data = self.microscope.task.state

        return jsonify(data)

    def delete(self):
        """
        Clean list of long-running tasks (running tasks persist).

        .. :quickref: Tasks; Clean collection of tasks

        :>header Accept: application/json

        :>header Content-Type: application/json
        """

        self.microscope.task.clean()
        data = self.microscope.task.state

        return jsonify(data)


class TaskAPI(MicroscopeView):
    def get(self, task_id):
        """
        Get JSON representation of a task

        .. :quickref: Tasks; Get task

        **Example request**:

        .. sourcecode:: http

          GET /task/db13a66787e1419bb06b1504e4d80b0c/ HTTP/1.1
          Accept: application/json

        **Example response**:

        .. sourcecode:: http

          HTTP/1.1 200 OK
          Vary: Accept
          Content-Type: application/json

          {
            "end_time": "2019-01-23 16-33-33", 
            "id": "db13a66787e1419bb06b1504e4d80b0c", 
            "return": [
            0.848622546386467, 
            0.6106785018091292, 
            ], 
            "start_time": "2019-01-23 16-33-13", 
            "status": "success"
          }

        """

        task = self.microscope.task.task_from_id(task_id)

        if not task_id:
            return abort(404)  # 404 Not Found

        # Return task state
        return jsonify(task.state)

    def delete(self, task_id):
        """
        Remove a particular task (fails if task is currently running).

        .. :quickref: Tasks; Remove a task

        :>header Accept: application/json

        :>header Content-Type: application/json
        """

        success = self.microscope.task.delete(task_id)

        if success:
            data = {"status": "success", "message": "task successfully deleted"}
        else:
            data = {
                "status": "fail",
                "message": "task could not be deleted, as it is currently running or does not exist",
            }

        return jsonify(data)


def construct_blueprint(microscope_obj):

    blueprint = Blueprint("task_blueprint", __name__)

    blueprint.add_url_rule(
        "/", view_func=TaskListAPI.as_view("task_list", microscope=microscope_obj)
    )

    blueprint.add_url_rule(
        "/<task_id>/", view_func=TaskAPI.as_view("task", microscope=microscope_obj)
    )

    return blueprint
