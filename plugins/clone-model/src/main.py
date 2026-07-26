from typing import Awaitable, Callable, Optional

from pydantic import BaseModel


class Action:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.valves = self.Valves()

    async def action(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> None:
        if not __user__:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Error: User context not found.",
                            "done": True,
                        },
                    }
                )
            return

        model_id = body.get("model")
        user_id = __user__.get("id")

        if not model_id:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Error: No active model selected.",
                            "done": True,
                        },
                    }
                )
            return

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Fetching model '{model_id}'...",
                        "done": False,
                    },
                }
            )

        try:
            from open_webui.models.models import ModelForm, Models

            source_model = await Models.get_model_by_id(model_id)
            if not source_model:
                raise Exception(f"Model '{model_id}' not found")

            base_id = f"{model_id}-clone-{user_id[:6]}"
            new_model_id = base_id
            clone_name = f"{source_model.name} (Copy)"

            suffix = 2
            while await Models.get_model_by_id(new_model_id):
                new_model_id = f"{base_id}-{suffix}"
                clone_name = f"{source_model.name} (Copy {suffix})"
                suffix += 1

            form = ModelForm(
                id=new_model_id,
                name=clone_name,
                meta=source_model.meta,
                params=source_model.params,
                base_model_id=source_model.base_model_id or model_id,
                access_grants=[
                    {
                        "principal_type": "user",
                        "principal_id": user_id,
                        "permission": "read",
                    },
                    {
                        "principal_type": "user",
                        "principal_id": user_id,
                        "permission": "write",
                    },
                ],
            )

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Creating clone '{clone_name}' in your workspace...",
                            "done": False,
                        },
                    }
                )

            model = await Models.insert_new_model(form, user_id)
            if not model:
                raise Exception("Database insertion returned no model")

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Successfully cloned model to your Workspace: {clone_name}",
                            "done": True,
                        },
                    }
                )

        except Exception as e:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Failed to clone model: {str(e)}",
                            "done": True,
                        },
                    }
                )
