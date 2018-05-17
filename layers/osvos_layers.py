from __future__ import division

import numpy as np
from PIL import Image

import torch
from torch.autograd import Variable
from torch.nn import functional as F


def logit(x):
    return np.log(x/(1-x+1e-08)+1e-08)


def sigmoid_np(x):
    return 1/(1+np.exp(-x))


def class_balanced_cross_entropy_loss(output, label, size_average=True, batch_average=True):
    """Define the class balanced cross entropy loss to train the network
    Args:
    output: Output of the network
    label: Ground truth label
    Returns:
    Tensor that evaluates the loss
    """

    # mask out ignored pixels
    mask = (label != 255).byte()
    output = output[mask].view(output.size(0), -1)
    label = label[mask].view(output.size(0), -1).float()

    num_labels_pos = torch.sum(label)
    num_labels_neg = torch.sum(1.0 - label)
    num_total = num_labels_pos + num_labels_neg

    output_gt_zero = torch.ge(output, 0).float()
    loss_val = torch.mul(output, (label - output_gt_zero)) - torch.log(
        1 + torch.exp(output - 2 * torch.mul(output, output_gt_zero)))

    loss_pos = torch.sum(-torch.mul(label, loss_val))
    loss_neg = torch.sum(-torch.mul(1.0 - label, loss_val))

    final_loss = num_labels_neg / num_total * loss_pos + num_labels_pos / num_total * loss_neg

    if size_average:
        final_loss /= np.prod(label.size())
    elif batch_average:
        final_loss /= label.size()[0]

    return final_loss


def center_crop(x, height, width):
    crop_h = torch.FloatTensor([x.size()[2]]).sub(height).div(-2)
    crop_w = torch.FloatTensor([x.size()[3]]).sub(width).div(-2)

    return F.pad(x, [
        crop_w.ceil().int()[0], crop_w.floor().int()[0],
        crop_h.ceil().int()[0], crop_h.floor().int()[0],
    ])


def upsample_filt(size):
    factor = (size + 1) // 2
    if size % 2 == 1:
        center = factor - 1
    else:
        center = factor - 0.5
    og = np.ogrid[:size, :size]
    return (1 - abs(og[0] - center) / factor) * \
           (1 - abs(og[1] - center) / factor)


# set parameters s.t. deconvolutional layers compute bilinear interpolation
# this is for deconvolution without groups
def interp_surgery(lay):
        m, k, h, w = lay.weight.data.size()
        if m != k:
            print('input + output channels need to be the same')
            raise ValueError
        if h != w:
            print('filters need to be square')
            raise ValueError
        filt = upsample_filt(h)

        for i in range(m):
            lay.weight[i, i, :, :].data.copy_(torch.from_numpy(filt))

        return lay.weight.data


if __name__ == '__main__':
    import os
    from mypath import Path

    # Output
    output = Image.open(os.path.join(Path.db_root_dir(), 'Annotations/480p/blackswan/00000.png'))
    output = np.asarray(output, dtype=np.float32)/255.0
    output = logit(output)
    output = Variable(torch.from_numpy(output)).cuda()

    # GroundTruth
    label = Image.open(os.path.join(Path.db_root_dir(), 'Annotations/480p/blackswan/00001.png'))
    label = Variable(torch.from_numpy(np.asarray(label, dtype=np.float32))/255.0).cuda()

    loss = class_balanced_cross_entropy_loss(output, label)
    print(loss)
