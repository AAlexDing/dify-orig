import json
import os
import random
from copy import deepcopy
from enum import Enum
from typing import Any, Union

from httpx import get
from yarl import URL

from core.tools.entities.common_entities import I18nObject
from core.tools.entities.tool_entities import ToolInvokeMessage, ToolParameter, ToolParameterOption
from core.tools.errors import ToolProviderCredentialValidationError
from core.tools.provider.builtin.comfyui.tools.comfyui_client import ComfyUiClient
from core.tools.tool.builtin_tool import BuiltinTool

SD_TXT2IMG_OPTIONS = {}
LORA_NODE = {
    "inputs": {"lora_name": "", "strength_model": 1, "strength_clip": 1, "model": ["11", 0], "clip": ["11", 1]},
    "class_type": "LoraLoader",
    "_meta": {"title": "Load LoRA"},
}
FluxGuidanceNode = {
    "inputs": {"guidance": 3.5, "conditioning": ["6", 0]},
    "class_type": "FluxGuidance",
    "_meta": {"title": "FluxGuidance"},
}


class ModelType(Enum):
    SD15 = 1
    SDXL = 2
    SD3 = 3
    FLUX = 4


class ComfyuiStableDiffusionTool(BuiltinTool):
    def _invoke(
        self, user_id: str, tool_parameters: dict[str, Any]
    ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        """
        invoke tools
        """
        # base url
        base_url = self.runtime.credentials.get("base_url", "")
        token = self.runtime.credentials.get("token", "")
        if not base_url:
            return self.create_text_message("Please input base_url")
        
        if tool_parameters.get("model"):
            self.runtime.credentials["model"] = tool_parameters["model"]

        model = self.runtime.credentials.get("model", None)
        if not model:
            return self.create_text_message("Please input model")

        # prompt
        prompt = tool_parameters.get("prompt", "")
        if not prompt:
            return self.create_text_message("Please input prompt")

        # get negative prompt
        negative_prompt = tool_parameters.get("negative_prompt", "")

        # get size
        width = tool_parameters.get("width", 1024)
        height = tool_parameters.get("height", 1024)

        # get steps
        steps = tool_parameters.get("steps", 1)

        # get sampler_name
        sampler_name = tool_parameters.get("sampler_name", "euler")

        # scheduler
        scheduler = tool_parameters.get("scheduler", "normal")

        # get cfg
        cfg = tool_parameters.get("cfg", 7.0)

        # get model type
        model_type = tool_parameters.get("model_type", ModelType.SD15.name)

        # get lora
        # supports up to 3 loras
        lora_list = []
        lora_strength_list = []
        if tool_parameters.get("lora_1"):
            lora_list.append(tool_parameters["lora_1"])
            lora_strength_list.append(tool_parameters.get("lora_strength_1", 1))
        if tool_parameters.get("lora_2"):
            lora_list.append(tool_parameters["lora_2"])
            lora_strength_list.append(tool_parameters.get("lora_strength_2", 1))
        if tool_parameters.get("lora_3"):
            lora_list.append(tool_parameters["lora_3"])
            lora_strength_list.append(tool_parameters.get("lora_strength_3", 1))

        return self.text2img(
            model=model,
            model_type=model_type,
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            sampler_name=sampler_name,
            scheduler=scheduler,
            cfg=cfg,
            lora_list=lora_list,
            lora_strength_list=lora_strength_list,
        )
        
    def validate_models(self) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        """
        validate models
        """
        try:
            base_url = self.runtime.credentials.get("base_url", None)
            if not base_url:
                raise ToolProviderCredentialValidationError("Please input base_url")
            model = self.runtime.credentials.get("model", None)
            if not model:
                raise ToolProviderCredentialValidationError("Please input model")
            token = self.runtime.credentials.get("token", "")

            api_url = str(URL(base_url) / "models" / "checkpoints")
            if token:
                api_url = api_url + f"?token={token}"
            response = get(url=api_url, timeout=(2, 10))
            if response.status_code != 200:
                raise ToolProviderCredentialValidationError("Failed to get models")
            else:
                models = response.json()
                if len([d for d in models if d == model]) > 0:
                    return self.create_text_message(json.dumps(models))
                else:
                    raise ToolProviderCredentialValidationError(f"model {model} does not exist")
        except Exception as e:
            raise ToolProviderCredentialValidationError(f"Failed to get models, {e}")

    def text2img(
        self,
        model: str,
        model_type: str,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
        sampler_name: str,
        scheduler: str,
        cfg: float,
        lora_list: list,
        lora_strength_list: list,
    ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        """
        generate image
        """
        base_url = self.runtime.credentials.get("base_url", "")
        token = self.runtime.credentials.get("token", "")
        if not base_url:
            return self.create_text_message("Please input base_url")
        comfyui_api = ComfyUiClient(base_url, token)
        
        if not SD_TXT2IMG_OPTIONS:
            current_dir = os.path.dirname(os.path.realpath(__file__))
            with open(os.path.join(current_dir, "txt2img.json")) as file:
                SD_TXT2IMG_OPTIONS.update(json.load(file))

        draw_options = deepcopy(SD_TXT2IMG_OPTIONS)
        draw_options["3"]["inputs"]["steps"] = steps
        draw_options["3"]["inputs"]["sampler_name"] = sampler_name
        draw_options["3"]["inputs"]["scheduler"] = scheduler
        draw_options["3"]["inputs"]["cfg"] = cfg
        # generate different image when using same prompt next time
        draw_options["3"]["inputs"]["seed"] = random.randint(0, 100000000)
        draw_options["4"]["inputs"]["ckpt_name"] = model
        draw_options["5"]["inputs"]["width"] = width
        draw_options["5"]["inputs"]["height"] = height
        draw_options["6"]["inputs"]["text"] = prompt
        draw_options["7"]["inputs"]["text"] = negative_prompt
        # if the model is SD3 or FLUX series, the Latent class should be corresponding to SD3 Latent
        if model_type in {ModelType.SD3.name, ModelType.FLUX.name}:
            draw_options["5"]["class_type"] = "EmptySD3LatentImage"

        if lora_list:
            # last Lora node link to KSampler node
            draw_options["3"]["inputs"]["model"][0] = "10"
            # last Lora node link to positive and negative Clip node
            draw_options["6"]["inputs"]["clip"][0] = "10"
            draw_options["7"]["inputs"]["clip"][0] = "10"
            # every Lora node link to next Lora node, and Checkpoints node link to first Lora node
            for i, (lora, strength) in enumerate(zip(lora_list, lora_strength_list), 10):
                if i - 10 == len(lora_list) - 1:
                    next_node_id = "4"
                else:
                    next_node_id = str(i + 1)
                lora_node = deepcopy(LORA_NODE)
                lora_node["inputs"]["lora_name"] = lora
                lora_node["inputs"]["strength_model"] = strength
                lora_node["inputs"]["strength_clip"] = strength
                lora_node["inputs"]["model"][0] = next_node_id
                lora_node["inputs"]["clip"][0] = next_node_id
                draw_options[str(i)] = lora_node

        # FLUX need to add FluxGuidance Node
        if model_type == ModelType.FLUX.name:
            last_node_id = str(10 + len(lora_list))
            draw_options[last_node_id] = deepcopy(FluxGuidanceNode)
            draw_options[last_node_id]["inputs"]["conditioning"][0] = "6"
            draw_options["3"]["inputs"]["positive"][0] = last_node_id

        try:
            result = comfyui_api.generate_image_by_prompt(prompt=draw_options)

            # get first image
            image = b""
            for node in result:
                for img in result[node]:
                    if img:
                        image = img
                        break

            return self.create_blob_message(
                blob=image, meta={"mime_type": "image/png"}, save_as=self.VariableKey.IMAGE.value
            )

        except Exception as e:
            return self.create_text_message(f"Failed to generate image: {str(e)}")

    def get_runtime_parameters(self) -> list[ToolParameter]:
        
        parameters = [
            ToolParameter(
                name="prompt",
                label=I18nObject(en_US="Prompt", zh_Hans="Prompt"),
                human_description=I18nObject(
                    en_US="Image prompt, you can check the official documentation of Stable Diffusion",
                    zh_Hans="图像提示词，您可以查看 Stable Diffusion 的官方文档",
                ),
                type=ToolParameter.ToolParameterType.STRING,
                form=ToolParameter.ToolParameterForm.LLM,
                llm_description="Image prompt of Stable Diffusion, you should describe the image "
                "you want to generate as a list of words as possible as detailed, "
                "the prompt must be written in English.",
                required=True,
            ),
        ]
        if self.runtime.credentials:
            base_url = self.runtime.credentials.get("base_url", "")
            token = self.runtime.credentials.get("token", "")
            if not base_url:
                return self.create_text_message("Please input base_url")
            comfyui_api = ComfyUiClient(base_url, token)
            try:
                models = comfyui_api.get_checkpoints()
                if not models:
                    self.create_text_message("Please check base_url and token")
                if len(models) != 0:
                    parameters.append(
                        ToolParameter(
                            name="model",
                            label=I18nObject(en_US="Model", zh_Hans="Model"),
                            human_description=I18nObject(
                                en_US="Model of Stable Diffusion or FLUX, "
                                "you can check the official documentation of Stable Diffusion or FLUX",
                                zh_Hans="Stable Diffusion 或者 FLUX 的模型，您可以查看 Stable Diffusion 的官方文档",
                            ),
                            type=ToolParameter.ToolParameterType.SELECT,
                            form=ToolParameter.ToolParameterForm.FORM,
                            llm_description="Model of Stable Diffusion or FLUX, "
                            "you can check the official documentation of Stable Diffusion or FLUX",
                            required=True,
                            default=models[0],
                            options=[
                                ToolParameterOption(value=i, label=I18nObject(en_US=i, zh_Hans=i)) for i in models
                            ],
                        )
                    )
                loras = comfyui_api.get_loras()
                if len(loras) != 0:
                    for n in range(1, 4):
                        parameters.append(
                            ToolParameter(
                                name=f"lora_{n}",
                                label=I18nObject(en_US=f"Lora {n}", zh_Hans=f"Lora {n}"),
                                human_description=I18nObject(
                                    en_US="Lora of Stable Diffusion, "
                                    "you can check the official documentation of Stable Diffusion",
                                    zh_Hans="Stable Diffusion 的 Lora 模型，您可以查看 Stable Diffusion 的官方文档",
                                ),
                                type=ToolParameter.ToolParameterType.SELECT,
                                form=ToolParameter.ToolParameterForm.FORM,
                                llm_description="Lora of Stable Diffusion, "
                                "you can check the official documentation of "
                                "Stable Diffusion",
                                required=False,
                                options=[
                                    ToolParameterOption(value=i, label=I18nObject(en_US=i, zh_Hans=i)) for i in loras
                                ],
                            )
                        )
                sample_methods, schedulers = comfyui_api.get_sample_methods()
                if len(sample_methods) != 0:
                    parameters.append(
                        ToolParameter(
                            name="sampler_name",
                            label=I18nObject(en_US="Sampling method", zh_Hans="Sampling method"),
                            human_description=I18nObject(
                                en_US="Sampling method of Stable Diffusion, "
                                "you can check the official documentation of Stable Diffusion",
                                zh_Hans="Stable Diffusion 的Sampling method，您可以查看 Stable Diffusion 的官方文档",
                            ),
                            type=ToolParameter.ToolParameterType.SELECT,
                            form=ToolParameter.ToolParameterForm.FORM,
                            llm_description="Sampling method of Stable Diffusion, "
                            "you can check the official documentation of Stable Diffusion",
                            required=True,
                            default=sample_methods[0],
                            options=[
                                ToolParameterOption(value=i, label=I18nObject(en_US=i, zh_Hans=i))
                                for i in sample_methods
                            ],
                        )
                    )
                if len(schedulers) != 0:
                    parameters.append(
                        ToolParameter(
                            name="scheduler",
                            label=I18nObject(en_US="Scheduler", zh_Hans="Scheduler"),
                            human_description=I18nObject(
                                en_US="Scheduler of Stable Diffusion, "
                                "you can check the official documentation of Stable Diffusion",
                                zh_Hans="Stable Diffusion 的Scheduler，您可以查看 Stable Diffusion 的官方文档",
                            ),
                            type=ToolParameter.ToolParameterType.SELECT,
                            form=ToolParameter.ToolParameterForm.FORM,
                            llm_description="Scheduler of Stable Diffusion, "
                            "you can check the official documentation of Stable Diffusion",
                            required=True,
                            default=schedulers[0],
                            options=[
                                ToolParameterOption(value=i, label=I18nObject(en_US=i, zh_Hans=i)) for i in schedulers
                            ],
                        )
                    )
                parameters.append(
                    ToolParameter(
                        name="model_type",
                        label=I18nObject(en_US="Model Type", zh_Hans="Model Type"),
                        human_description=I18nObject(
                            en_US="Model Type of Stable Diffusion or Flux, "
                            "you can check the official documentation of Stable Diffusion or Flux",
                            zh_Hans="Stable Diffusion 或 FLUX 的模型类型，"
                            "您可以查看 Stable Diffusion 或 Flux 的官方文档",
                        ),
                        type=ToolParameter.ToolParameterType.SELECT,
                        form=ToolParameter.ToolParameterForm.FORM,
                        llm_description="Model Type of Stable Diffusion or Flux, "
                        "you can check the official documentation of Stable Diffusion or Flux",
                        required=True,
                        default=ModelType.SD15.name,
                        options=[
                            ToolParameterOption(value=i, label=I18nObject(en_US=i, zh_Hans=i))
                            for i in ModelType.__members__
                        ],
                    )
                )
            except Exception as e:
                print(e)

        return parameters
