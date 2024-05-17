import os
import torch
import diffusers

class ImageGenerator:
    def __init__(self, config, device=None):
        self.device = device
        if self.device is None:
            self.device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        self.config = config
        self.pipeline = self._load_pipeline()
        self.pipeline.unet = torch.compile(self.pipeline.unet, mode="reduce-overhead", fullgraph=True)
        self.generator = torch.Generator(device=self.device)

    def _load_pipeline(self):
        ckpt_type = self.config["checkpoint_type"]
        if ckpt_type == "safetensors":
            pipeline = diffusers.StableDiffusionXLPipeline.from_single_file(self.config["model_ckpt"]).to(self.device)
        elif ckpt_type == "lora":
            base_model_ckpt = self.config["base_model_ckpt"]
            sd_model_type = self.config["sd_type"]
            if sd_model_type == "XL":
                pipeline = diffusers.StableDiffusionXLPipeline.from_single_file(base_model_ckpt).to(self.device)
            else:
                pipeline = diffusers.StableDiffusionPipeline.from_pretrained(base_model_ckpt).to(self.device)
            pipeline.load_lora_weights(self.config["model_ckpt"])
        elif ckpt_type == "diffusers":
            pipeline = diffusers.StableDiffusionPipeline.from_pretrained(self.config["model_ckpt"]).to(self.device)
        else:
            raise ValueError(f"Unknown checkpoint type: {ckpt_type}")
        return pipeline

    def __call__(self, prompt, seed, h=None, w=None, steps=None, cfg=None):
        h = h or self.config["height"]
        w = w or self.config["width"]
        steps = steps or self.config["steps"]
        cfg = cfg or self.config["cfg"]

        self.generator.manual_seed(seed)
        image_latents = torch.randn((1, self.pipeline.unet.config.in_channels, h // 8, w // 8), generator=self.generator, device=self.device)
        pil_images = self.pipeline(
            prompt,
            latents=image_latents,
            height=h,
            width=w,
            guidance_scale=cfg,
            num_images_per_prompt=1,
            num_inference_steps=steps,
        ).images
        checked_image = pil_images[0]
        torch.cuda.empty_cache()
        return checked_image