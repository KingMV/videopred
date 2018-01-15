#!/usr/bin/python
# -*- coding: UTF-8 -*-

import torch
from torch import nn
from torch.autograd import Variable

from DiscriminativeCell import DiscriminativeCell
from GenerativeCell import GenerativeCell

# Define some constants
OUT_LAYER_SIZE = (3,) + tuple(2 ** p for p in range(4, 10))
ERR_LAYER_SIZE = tuple(size * 2 for size in OUT_LAYER_SIZE)
IN_LAYER_SIZE = (3,) + ERR_LAYER_SIZE


class PrednetModel(nn.Module):
    """
    Build the Prednet model
    """

    def __init__(self, error_size_list):
        super(PrednetModel, self).__init__()
        self.number_of_layers = len(error_size_list)
        for layer in range(0, self.number_of_layers):
            setattr(self, 'discriminator_' + str(layer + 1), DiscriminativeCell(
                input_size={'input': IN_LAYER_SIZE[layer], 'state': OUT_LAYER_SIZE[layer]},
                hidden_size=OUT_LAYER_SIZE[layer],
                first=(not layer)
            ))
            setattr(self, 'generator_' + str(layer + 1), GenerativeCell(
                input_size={'error': ERR_LAYER_SIZE[layer], 'up_state':
                    OUT_LAYER_SIZE[layer + 1] if layer != self.number_of_layers - 1 else 0},
                hidden_size=OUT_LAYER_SIZE[layer],
                error_init_size=error_size_list[layer]
            ))

    def forward(self, bottom_up_input, error, state):

        # generative branch
        up_state = None
        for layer in reversed(range(0, self.number_of_layers)):
            state[layer] = getattr(self, 'generator_' + str(layer + 1))(
                error[layer], up_state, state[layer]
            )
            up_state = state[layer][0]

        # discriminative branch
        for layer in range(0, self.number_of_layers):
            # error[layer] = getattr(self, 'discriminator_' + str(layer + 1))(
            #     layer and error[layer - 1] or bottom_up_input,
            #     state[layer][0]
            # )
            if layer > 0:
                error[layer] = getattr(self, 'discriminator_' + str(layer + 1))(
                error[layer - 1], state[layer][0]
            )
            else:
                error[layer] = getattr(self, 'discriminator_' + str(layer + 1))(
                    bottom_up_input, state[layer][0]
                )

        return error, state


class _BuildOneLayerModel(nn.Module):
    """
    Build a one layer Prednet model
    """

    def __init__(self, error_size_list):
        super(_BuildOneLayerModel, self).__init__()
        self.discriminator = DiscriminativeCell(
            input_size={'input': IN_LAYER_SIZE[0], 'state': OUT_LAYER_SIZE[0]},
            hidden_size=OUT_LAYER_SIZE[0],
            first=True
        )
        self.generator = GenerativeCell(
            input_size={'error': ERR_LAYER_SIZE[0], 'up_state': 0},
            hidden_size=OUT_LAYER_SIZE[0],
            error_init_size=error_size_list[0]
        )

    def forward(self, bottom_up_input, prev_error, state):
        state = self.generator(prev_error, None, state)
        error = self.discriminator(bottom_up_input, state[0])
        return error, state


class _BuildTwoLayerModel(nn.Module):
    """
    Build a two layer Prednet model
    """

    def __init__(self, error_size_list):
        super(_BuildTwoLayerModel, self).__init__()
        self.discriminator_1 = DiscriminativeCell(
            input_size={'input': IN_LAYER_SIZE[0], 'state': OUT_LAYER_SIZE[0]},
            hidden_size=OUT_LAYER_SIZE[0],
            first=True
        )
        self.discriminator_2 = DiscriminativeCell(
            input_size={'input': IN_LAYER_SIZE[1], 'state': OUT_LAYER_SIZE[1]},
            hidden_size=OUT_LAYER_SIZE[1]
        )
        self.generator_1 = GenerativeCell(
            input_size={'error': ERR_LAYER_SIZE[0], 'up_state': OUT_LAYER_SIZE[1]},
            hidden_size=OUT_LAYER_SIZE[0],
            error_init_size=error_size_list[0]
        )
        self.generator_2 = GenerativeCell(
            input_size={'error': ERR_LAYER_SIZE[1], 'up_state': 0},
            hidden_size=OUT_LAYER_SIZE[1],
            error_init_size=error_size_list[1]
        )

    def forward(self, bottom_up_input, error, state):
        state[1] = self.generator_2(error[1], None, state[1])
        state[0] = self.generator_1(error[0], state[1][0], state[0])
        error[0] = self.discriminator_1(bottom_up_input, state[0][0])
        error[1] = self.discriminator_2(error[0], state[1][0])
        return error, state


def _test_one_layer_model():
    print('\nCreate the input image')
    input_image = Variable(torch.rand(1, 3, 8, 12))

    print('Input has size', list(input_image.data.size()))

    error_init_size = (1, 6, 8, 12)
    print('The error initialisation size is', error_init_size)

    print('Define a 1 layer Prednet')
    model = _BuildOneLayerModel((error_init_size,))

    print('Forward input and state to the model')
    state = None
    error = None
    error, state = model(input_image, prev_error=error, state=state)

    print('The error has size', list(error.data.size()))
    print('The state has size', list(state[0].data.size()))


def _test_two_layer_model():
    print('\nCreate the input image')
    input_image = Variable(torch.rand(1, 3, 8, 12))

    print('Input has size', list(input_image.data.size()))

    error_init_size_list = ((1, 6, 8, 12), (1, 32, 4, 6))
    print('The error initialisation sizes are', error_init_size_list)

    print('Define a 2 layer Prednet')
    model = _BuildTwoLayerModel(error_init_size_list)

    print('Forward input and state to the model')
    state = [None] * 2
    error = [None] * 2
    error, state = model(input_image, error=error, state=state)

    for layer in range(0, 2):
        print('Layer', layer + 1, 'error has size', list(error[layer].data.size()))
        print('Layer', layer + 1, 'state has size', list(state[layer][0].data.size()))


def _test_L_layer_model():

    max_number_of_layers = 5
    for L in range(0, max_number_of_layers):
        print('\n---------- Test', str(L + 1), 'layer network ----------')

        print('Create the input image')
        input_image = Variable(torch.rand(1, 3, 4 * 2 ** L, 6 * 2 ** L))

        print('Input has size', list(input_image.data.size()))

        error_init_size_list = tuple(
            (1, ERR_LAYER_SIZE[l], 4 * 2 ** (L-l), 6 * 2 ** (L-l)) for l in range(0, L + 1)
        )
        print('The error initialisation sizes are', error_init_size_list)

        print('Define a', str(L + 1), 'layer Prednet')
        model = PrednetModel(error_init_size_list)

        print('Forward input and state to the model')
        state = [None] * (L + 1)
        error = [None] * (L + 1)
        error, state = model(input_image, error=error, state=state)

        for layer in range(0, L + 1):
            print('Layer', layer + 1, 'error has size', list(error[layer].data.size()))
            print('Layer', layer + 1, 'state has size', list(state[layer][0].data.size()))


def _test_training():
    number_of_layers = 3
    T = 6  # sequence length
    max_epoch = 10  # number of epochs
    lr = 1e-1       # learning rate

    # set manual seed
    torch.manual_seed(0)

    L = number_of_layers - 1
    print('\n---------- Train a', str(L + 1), 'layer network ----------')
    print('Create the input image and target sequences')
    input_sequence = Variable(torch.rand(T, 1, 3, 4 * 2 ** L, 6 * 2 ** L))
    print('Input has size', list(input_sequence.data.size()))

    error_init_size_list = tuple(
        (1, ERR_LAYER_SIZE[l], 4 * 2 ** (L - l), 6 * 2 ** (L - l)) for l in range(0, L + 1)
    )
    print('The error initialisation sizes are', error_init_size_list)
    target_sequence = Variable(torch.zeros(T, *error_init_size_list[0]))

    print('Define a', str(L + 1), 'layer Prednet')
    model = PrednetModel(error_init_size_list)

    print('Create a MSE criterion')
    loss_fn = nn.MSELoss()

    print('Run for', max_epoch, 'iterations')
    for epoch in range(0, max_epoch):
        state = [None] * (L + 1)
        error = [None] * (L + 1)
        loss = 0
        for t in range(0, T):
            error, state = model(input_sequence[t], error, state)
            loss += loss_fn(error[0], target_sequence[t])

        print(' > Epoch {:2d} loss: {:.3f}'.format((epoch + 1), loss.data[0]))

        # zero grad parameters
        model.zero_grad()

        # compute new grad parameters through time!
        loss.backward()

        # learning_rate step against the gradient
        for p in model.parameters():
            p.data.sub_(p.grad.data * lr)


def _main():
    _test_one_layer_model()
    _test_two_layer_model()
    _test_L_layer_model()
    _test_training()


if __name__ == '__main__':
    _main()
