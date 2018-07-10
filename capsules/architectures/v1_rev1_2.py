#from operations.capsule_operations import *
import sys
sys.path.insert(0, 'capsules/operations')
from routing import *
from capsule_operations import *

import tensorflow as tf
import numpy as np
import collections


sys.path.insert(0, 'lib/')
from architecture import architecture_base


# Rev 10 is about really focussing on local "patch" based routing

# Rev10_2 is just a version with fewer weights to fit into most GPU memories.

# 0v_rev11_4_verylowparams_1_residual_highres -> this is just reducing the number of routing iterations (i use 3 here)

# 0v,12,3  (2->4) => Change ending to just add the input (not multipliers) and make initial conv deeper, make end conv  and remove squash bias


# 0v,13, 1, (2 -> 4) => Main change is that the nework is deeper both before and after capsule layer. Output is different in the sense that it is now a simple addition. BUT also, change the number of routing iterations to 2, not 3.

# This version is inspired from : v0_rev13_1_verylowparams_10_residual_highres
# Main changes: Be compatible with new validation model, Inherit from the abstract class
# Upcoming changes across revisions of this version:
# - More weights and testing overfitting using the validation set
# - using a 3x3 or 5x5 kernel for the convolutional capsules, instead of the current 1x1
# - increasing from 2 routing iterations to 3 iterations, etc...

# 1,1, (1->2) => number of weights increased to check overfitting ( went from 5m weight to ... weights)


Results = collections.namedtuple('Results', ('output', 'capslayer', 'capsres'))

class architecture(architecture_base):
    def build(self, input_images):
        #input images = [batch, height,width]
        its = input_images.get_shape().as_list()
        print(">>>>> Initial Convolution")
        print(input_images.get_shape().as_list())
        layer1 = tf.expand_dims(input_images, axis=3)
        layer1 = tf.layers.conv2d(layer1, 256, 9, padding='same', name='InitConv', activation=tf.nn.relu)
        for i in range(6):
            layer1 = tf.layers.conv2d(layer1, 256, 9, padding='same', name='InitConv'+str(i), activation=tf.nn.relu)
        layer2 = layer1
        layer2 = tf.layers.conv2d(layer2, 256, 9, padding='same', name='linear_conv', activation=None)
        # [batch, 128,128, 256]
        tmp = layer2.get_shape().as_list()
        layer2 = tf.expand_dims(layer2, axis=4)
        layer2 = tf.reshape(layer2, [tmp[0],tmp[1],tmp[2]] + [8, 32])
        layer2 = tf.transpose(layer2, [0,3,4,1,2])  # [batch, 8, num_ch, height, width]


        #layer2 = tf.subtract(layer2, tf.reduce_mean(layer2, axis=1, keepdims=True))
        layer3 = convolutional_capsule_layer_v2(layer2,1,1,'ConvCaps1',output_kernel_vec_dim=4,  num_output_channels=4, strides=[1,1], type="SAME", num_routing=2, use_matrix_bias=True, use_squash_bias=True)
        print(layer3.get_shape().as_list())
        layer3_keep = layer3
        #layer3 = tf.subtract(layer3, tf.reduce_mean(layer3, axis=1, keepdims=True)) # doing this means that the squash bias is there purely to infuence routing, rather than the overall output; for any bias that is required, it will be supplied by the convolution in the subsequent layers
        print(layer3.get_shape().as_list())
        layer3 = tf.transpose(tf.reshape(tf.transpose(layer3, [0,3,4,1,2]), [its[0],128,128,-1,1]), [0,3,4,1,2]) # for the image summaries
        layer3_keep = tf.transpose(tf.reshape(tf.transpose(layer3_keep, [0,3,4,1,2]), [its[0],128,128,-1,1]), [0,3,4,1,2]) # for the image summaries
        print(layer3.get_shape().as_list())

        layer4 = tf.squeeze(tf.transpose(layer3, [0,3,4,1,2]), axis=4)
        layer4a = layer4
        layer4b = layer4
        layer4c = layer4
        for i in range(6):
            layer4a = tf.layers.conv2d(layer4a, 256, 5, strides=(1,1), padding='same', name="capstooutput_tanh"+str(i), activation=tf.nn.tanh)
        for i in range(6):
            layer4b = tf.layers.conv2d(layer4b, 256, 5, strides=(1,1), padding='same', name="capstooutput_relu"+str(i), activation=tf.nn.relu)
        for i in range(8): # deep but provides ability to pull the background characteristics together
            layer4c = tf.layers.conv2d(layer4c, 16, 5, strides=(1,1), padding='same', name="capstooutput_linear"+str(i), activation=None)
        layer4 = tf.concat([layer4a, layer4b, layer4c, layer4], axis=3)
        layer4 = tf.layers.conv2d(layer4, 1, 9, strides=(1,1), padding='same', name="capstooutput_all"+str(4), activation=None)

        output = layer4
        output = tf.squeeze(output, axis=3)
        '''with tf.device('/cpu:0'):
            with tf.name_scope('output_addition'):
                weight_1 = tf.get_variable('weight1',[1],initializer=tf.constant_initializer(0.001), dtype=tf.float32, trainable=True)
                weight_2 = tf.get_variable('weight2',[1],initializer=tf.constant_initializer(3.0), dtype=tf.float32, trainable=True)
        output = layer4
        output = tf.squeeze(output, axis=3)
        #output = tf.layers.conv2d(output, 1, 1, strides=(1,1), padding='same', name="thefinaloutput."+str(4), use_bias=False, activation=None) # ReLU ?
        output = tf.add((output * tf.abs(weight_1)),  (input_images * tf.abs(weight_2)) )
        #output = tf.concat([tf.expand_dims(output, axis=3), tf.expand_dims(input_images,axis=3)], axis=3)'''

        output = tf.add(output, input_images)
        output = tf.expand_dims(output, axis=3)
        for i in range(4):
            output = tf.layers.conv2d(output, 8, 5, strides=(1,1), padding='same', name="f"+str(i), activation=tf.nn.relu)
        output = tf.layers.conv2d(output, 1, 5, strides=(1,1), padding='same', name="f."+str(i), activation=tf.nn.relu)
        output = tf.squeeze(output, axis=3)


        print(output.get_shape().as_list())
        capslayer = tf.transpose(tf.squeeze(layer3_keep, axis=2), [1,2,3,0])
        result = Results(output, capslayer, layer4 )
        print(">>>>> Graph Built!")

        with tf.device('/cpu:0'):
            global_step = tf.get_variable('global_step', [], initializer=tf.constant_initializer(0), trainable=False) # [] [unfinished]
            global_step = tf.add(global_step, 1)
        return result


    def loss_func(self, input_images, ground_truth, validation_input_images, validation_ground_truth):
        input_images = tf.expand_dims(input_images, axis=3)
        ground_truth = tf.expand_dims(ground_truth, axis=3)
        mini_batch_size = input_images.get_shape().as_list()[0]
        #input_images = tf.image.crop_and_resize(input_images, [[0.25,0.25, 0.75,0.75]]*mini_batch_size, list(range(mini_batch_size)), [64,64]  )
        #ground_truth = tf.image.crop_and_resize(ground_truth, [[0.25,0.25, 0.75,0.75]]*mini_batch_size, list(range(mini_batch_size)), [64,64]  )
        #input_images = tf.image.crop_and_resize(input_images, [[0.375,0.375,0.625,0.625]]*mini_batch_size, list(range(mini_batch_size)), [64,64]  )
        #ground_truth = tf.image.crop_and_resize(ground_truth, [[0.375,0.375,0.625,0.625]]*mini_batch_size, list(range(mini_batch_size)), [64,64]  )
        input_images = tf.image.crop_and_resize(input_images, [[0.25,0.25,0.75,0.75]]*mini_batch_size, list(range(mini_batch_size)), [128,128]  )
        ground_truth = tf.image.crop_and_resize(ground_truth, [[0.25,0.25,0.75,0.75]]*mini_batch_size, list(range(mini_batch_size)), [128,128]  )
        input_images = tf.squeeze(input_images, axis=3)
        ground_truth = tf.squeeze(ground_truth, axis=3)

        print(">>>Start Building Architecture.")
        res = self.build(input_images)
        print(">>>Finished Building Architecture.")
        output = res.output

        print(">>> Run on validation set")
        validation_res = self.build(validation_input_images)
        validation_output = validation_res.output
        print(">>> Find MSE for the validation set")
        v_diff = tf.subtract(validation_ground_truth, validation_output)
        v_MSE_loss = tf.reduce_mean(tf.norm(v_diff, axis=[1,2]))
        with tf.name_scope('validation'):
            tf.summary.scalar("validation_total_loss", v_MSE_loss)
        print(">>>Some Maths on result")
        print(">>>> Find Difference")
        difference = tf.subtract(ground_truth, output)
        print(">>>> Find Norm")
        L2_norm = tf.norm(difference, axis=[1,2])
        print(">>>> Find Mean of Norm")
        batch_loss = tf.reduce_mean(L2_norm)
        #print(">>>> New batch loss regulariser metric")
        #diff1 = tf.abs(tf.subtract(output, input_images))
        #zerovec1 = tf.zeros(shape=(1,1), dtype=tf.float32)
        #bool_mask = tf.not_equal(diff1, zerovec1)
        #diff1_omit = tf.boolean_mask(diff1, bool_mask)
        #diff1_omit = tf.reduce_mean(diff1_omit)
        #batch_loss = batch_loss + diff1_omit

        print(">>>> Find + and - loss")
        positive_loss =  tf.reduce_sum(tf.boolean_mask(difference, tf.greater(difference, 0.)))
        negative_loss =  tf.reduce_sum(tf.boolean_mask(difference, tf.less(difference, 0.)))

        print(">>>> PSNR and SSIM")
        psnr = tf.image.psnr(tf.expand_dims(ground_truth, axis=3), tf.expand_dims(output, axis=3), max_val=1114) #1114 3480
        ssim = tf.image.ssim(tf.expand_dims(ground_truth, axis=3), tf.expand_dims(output, axis=3), max_val=1114) #1114 3480

        print(">>>> PSNR Stats")
        max_psnr = tf.reduce_max(psnr)
        min_psnr = tf.reduce_min(psnr)
        mean_psnr = tf.reduce_mean(psnr)


        print(">>>> SSIM Stats")
        max_ssim = tf.reduce_max(ssim)
        min_ssim = tf.reduce_min(ssim)
        mean_ssim = tf.reduce_mean(ssim)


        print(">>>> Find Mean Loss")
        with tf.name_scope('total'):
            print(">>>>>> Add to collection")
            tf.add_to_collection('losses', batch_loss)
            print(">>>>>> Creating summary")
            tf.summary.scalar(name='batch_L2_reconstruction_cost', tensor=batch_loss)
            print(">>>> Add result to collection of loss results for this tower")
            all_losses = tf.get_collection('losses') # [] , this_tower_scope) # list of tensors returned
            total_loss = tf.add_n(all_losses) # element-wise addition of the list of tensors
            #print(total_loss.get_shape().as_list())
            tf.summary.scalar('total_loss', total_loss)
        print(">>>> Add results to output")
        with tf.name_scope('accuracy'):
            tf.summary.scalar('max_psnr', max_psnr)
            tf.summary.scalar('min_psnr', min_psnr)
            tf.summary.scalar('mean_psnr', mean_psnr)
            tf.summary.scalar('max_ssim', max_ssim)
            tf.summary.scalar('min_ssim', min_ssim)
            tf.summary.scalar('mean_ssim', mean_ssim)
            tf.summary.scalar('positive_loss', positive_loss)
            tf.summary.scalar('negative_loss', tf.multiply(negative_loss, -1.))
            model_output_f1 = tf.expand_dims(tf.slice(output, [0,0,0], [1, -1,-1]), axis=3)
            model_input_f1 = tf.expand_dims(tf.slice(input_images, [0,0,0], [1, -1,-1]), axis=3)
            model_gt_f1 = tf.expand_dims(tf.slice(ground_truth, [0,0,0], [1, -1,-1]), axis=3)
            tf.summary.image('model_output',  model_output_f1)
            tf.summary.image('model_input',  model_input_f1)
            tf.summary.image('model_ground_truth',  model_gt_f1)
            tf.summary.image('model_diff_gt_output',  model_gt_f1 - model_output_f1)
            tf.summary.image('model_diff_input_output',  model_input_f1 - model_output_f1)

            capslayer = tf.slice(res.capslayer, [0,0,0,0], [-1,-1,-1,1])
            tf.summary.image('capslayer_output', capslayer, max_outputs=32)

            capslayer_mean = tf.reduce_mean(capslayer, axis=0, keepdims=True)
            capslayer_res = capslayer - capslayer_mean
            tf.summary.image('capslayer_output_res', capslayer_res, max_outputs=32)

            capsres = tf.slice(res.capsres, [0,0,0,0], [1,-1,-1, -1])
            tf.summary.image('capsres', capsres, max_outputs=1)

        diagnostics = {'max_psnr': max_psnr, 'min_psnr': min_psnr, 'mean_psnr': mean_psnr, 'max_ssim':max_ssim, 'min_ssim':min_ssim, 'mean_ssim':mean_ssim, 'positive_loss':positive_loss, 'negative_loss':negative_loss, 'total_loss':total_loss}
        return output, batch_loss, diagnostics