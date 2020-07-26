from __future__ import print_function

import argparse
import os
import sys
import time
import tensorflow as tf
import numpy as np
from scipy import misc

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from model import PSPNet101, PSPNet50
from tools import *



class MyPSPNET():
    def __init__(self):
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.BASE_DIR = BASE_DIR

        self.ADE20k_param = {'crop_size': [473, 473],
                        'num_classes': 150,
                        'model': PSPNet50}
        self.cityscapes_param = {'crop_size': [720, 720],
                            'num_classes': 19,
                            'model': PSPNet101}

        self.SAVE_DIR = BASE_DIR + '/output/'
        self.SNAPSHOT_DIR = BASE_DIR + '/models/pspnet101-cityscapes/'

    # def get_arguments(self):
    #     parser = argparse.ArgumentParser(description="Reproduced PSPNet")
    #     parser.add_argument("--img-path", type=str, default='./input/water.jpg',
    #                         help="Path to the RGB image file.")
    #     parser.add_argument("--checkpoints", type=str, default=SNAPSHOT_DIR,
    #                         help="Path to restore weights.")
    #     parser.add_argument("--save-dir", type=str, default=SAVE_DIR,
    #                         help="Path to save output.")
    #     parser.add_argument("--flipped-eval", action="store_true",
    #                         help="whether to evaluate with flipped img.")
    #     parser.add_argument("--dataset", type=str, default='cityscapes',
    #                         choices=['ade20k', 'cityscapes'],
    #                         required=False)
    #     return parser.parse_args()

    def save(self, saver, sess, logdir, step):
        model_name = 'model.ckpt'
        checkpoint_path = os.path.join(logdir, model_name)

        if not os.path.exists(logdir):
            os.makedirs(logdir)
        saver.save(sess, checkpoint_path, global_step=step)
        print('The checkpoint has been created.')

    def load(self, saver, sess, ckpt_path):
        saver.restore(sess, ckpt_path)
        print("Restored model parameters from {}".format(ckpt_path))

    def detect(self, filepath):
        # args = get_arguments()

        args_dataset = 'cityscapes'
        args_flipped_eval = True
        args_save_dir = self.SAVE_DIR

        # load parameters
        if args_dataset == 'ade20k':
            param = self.ADE20k_param
            args_checkpoints = self.BASE_DIR + '/models/pspnet50-ade20k'
        elif args_dataset == 'cityscapes':
            param = self.cityscapes_param
            args_checkpoints = self.BASE_DIR + '/models/pspnet101-cityscapes/'
        else:
            param = self.ADE20k_param

        crop_size = param['crop_size']
        num_classes = param['num_classes']
        PSPNet = param['model']

        # preprocess images
        img, filename = load_img(filepath)
        img_shape = tf.shape(img)
        h, w = (tf.maximum(crop_size[0], img_shape[0]), tf.maximum(crop_size[1], img_shape[1]))
        img = preprocess(img, h, w)

        # Create network.
        net = PSPNet({'data': img}, is_training=False, num_classes=num_classes)
        with tf.variable_scope('', reuse=True):
            flipped_img = tf.image.flip_left_right(tf.squeeze(img))
            flipped_img = tf.expand_dims(flipped_img, dim=0)
            net2 = PSPNet({'data': flipped_img}, is_training=False, num_classes=num_classes)

        raw_output = net.layers['conv6']

        # Do flipped eval or not
        if args_flipped_eval:
            flipped_output = tf.image.flip_left_right(tf.squeeze(net2.layers['conv6']))
            flipped_output = tf.expand_dims(flipped_output, dim=0)
            raw_output = tf.add_n([raw_output, flipped_output])

        # Predictions.
        raw_output_up = tf.image.resize_bilinear(raw_output, size=[h, w], align_corners=True)
        raw_output_up = tf.image.crop_to_bounding_box(raw_output_up, 0, 0, img_shape[0], img_shape[1])
        raw_output_up = tf.argmax(raw_output_up, axis=3)
        pred = decode_labels(raw_output_up, img_shape, num_classes)

        # Init tf Session
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True
        sess = tf.Session(config=config)
        init = tf.global_variables_initializer()

        sess.run(init)

        restore_var = tf.global_variables()

        ckpt = tf.train.get_checkpoint_state(args_checkpoints, "checkpoint.txt")
        print("=== args_checkpoints", args_checkpoints)
        if ckpt and ckpt.model_checkpoint_path:
            loader = tf.train.Saver(var_list=restore_var)
            load_step = int(os.path.basename(ckpt.model_checkpoint_path).split('-')[1])
            self.load(loader, sess, ckpt.model_checkpoint_path)
        else:
            print('No checkpoint file found.')

        preds = sess.run(pred)

        if not os.path.exists(args_save_dir):
            os.makedirs(args_save_dir)
        misc.imsave(args_save_dir + filename, preds[0])
        return preds[0]



if __name__ == '__main__':
    p = MyPSPNET()
    p.detect('./input/ade20k.jpg')
