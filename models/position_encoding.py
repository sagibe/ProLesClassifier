"""
Various positional encodings for the transformer.
Modified from DETR (https://github.com/facebookresearch/detr)
"""
import math
import torch
from torch import nn

from utils.util import NestedTensor

# position encoding for 3 dims
class PositionEmbeddingSine(nn.Module):
    """
    This is a more standard version of the position embedding, very similar to the one
    used by the Attention is all you need paper, generalized to work on images.
    """
    def __init__(self, num_pos_feats=64, num_frames = 36, temperature=10000, normalize=False, scale=None, device='cuda'):
        super().__init__()
        self.num_pos_feats = num_pos_feats
        self.temperature = temperature
        self.normalize = normalize
        self.frames = num_frames
        self.device = device
        if scale is not None and normalize is False:
            raise ValueError("normalize should be True if scale is passed")
        if scale is None:
            scale = 2 * math.pi
        self.scale = scale

    def forward(self, scan):
        d, em, h, w = scan.size()
        mask = torch.ones((self.frames, h, w))
        mask = mask.reshape(1, self.frames,h,w).to(self.device)
        # assert mask is not None
        # not_mask = ~mask
        z_embed = mask.cumsum(1, dtype=torch.float32)
        y_embed = mask.cumsum(2, dtype=torch.float32)
        x_embed = mask.cumsum(3, dtype=torch.float32)
        if self.normalize:
            eps = 1e-6
            z_embed = z_embed / (z_embed[:, -1:, :, :] + eps) * self.scale
            y_embed = y_embed / (y_embed[:, :, -1:, :] + eps) * self.scale
            x_embed = x_embed / (x_embed[:, :, :, -1:] + eps) * self.scale

        dim_t = torch.arange(self.num_pos_feats, dtype=torch.float32, device=scan.device)
        dim_t = self.temperature ** (2 * (dim_t // 2) / self.num_pos_feats)

        pos_x = x_embed[:, :, :, :, None] / dim_t
        pos_y = y_embed[:, :, :, :, None] / dim_t
        pos_z = z_embed[:, :, :, :, None] / dim_t
        pos_x = torch.stack((pos_x[:, :, :, :, 0::2].sin(), pos_x[:, :, :, :, 1::2].cos()), dim=5).flatten(4)
        pos_y = torch.stack((pos_y[:, :, :, :, 0::2].sin(), pos_y[:, :, :, :, 1::2].cos()), dim=5).flatten(4)
        pos_z = torch.stack((pos_z[:, :, :, :, 0::2].sin(), pos_z[:, :, :, :, 1::2].cos()), dim=5).flatten(4)
        pos = torch.cat((pos_z, pos_y, pos_x), dim=4).permute(0, 1, 4, 2, 3)
        return pos


def build_position_encoding(args):
    N_steps = args.MODEL.TRANSFORMER.EMBED_SIZE // 3
    if args.MODEL.POSITION_EMBEDDING.TYPE in ('v2', 'sine'):
        # TODO find a better way of exposing other arguments
        position_embedding = PositionEmbeddingSine(N_steps, num_frames=args.MODEL.POSITION_EMBEDDING.Z_SIZE, normalize=True, device=args.DEVICE)
    else:
        raise ValueError(f"not supported {args.position_embedding}")

    return position_embedding
