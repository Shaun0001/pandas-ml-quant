import torch as t
import torch.nn as nn


class DifferentiableArgmax(nn.Module):

    def __init__(self, nr_of_categories, beta=1e10):
        super().__init__()
        self.y_range = t.arange(0, nr_of_categories).float()
        self.softmax = nn.Softmax(dim=-1)
        self.beta = t.tensor(beta).float()

    def forward(self, y):
        return t.sum(self.softmax(y * self.beta) * self.y_range, dim=-1)


class ParabolicPenaltyLoss(nn.Module):

    def __init__(self, nr_of_categories, delta=1.0, beta=1e10):
        super().__init__()
        self.argmax = DifferentiableArgmax(nr_of_categories, beta)
        self.offset = t.tensor(delta / 2).float()
        self.f = t.tensor((nr_of_categories + delta) / nr_of_categories).float()

    def forward(self, y_pred, y_true):
        return ((self.argmax(y_pred) + self.offset) - (self.argmax(y_true)) * self.f) ** 2


class TailedCategoricalCrossentropyLoss(nn.Module):

    def __init__(self, nr_of_categories: int, alpha=0.1, beta=1e10, delta=1.0, reduction='none'):
        """
        assuming that we have discretized something like returns where we have less observations in the tails.
        If we want to train a neural net to place returns into the expected bucket we want to penalize if the
        prediction is too close to the mean. we rather want to be pessimistic and force the predictor to
        encounter the tails.

        :param nr_of_categories: number of categories aka length of the one hot encoded vectors
        :param alpha: describes the steepness of the parabola
        :param beta: used for the differentiable_argmax
        :param delta: is used to un-evenly skew the loss to the outer bounds. 0 now skew > bigger skew
        :return: returns a keras loss function
        """
        super().__init__()
        self.parabolic_penalty = ParabolicPenaltyLoss(nr_of_categories, delta, beta)
        self.categorical_crossentropy = nn.CrossEntropyLoss()
        self.reduction = reduction
        self.alpha = alpha

    def forward(self, y_pred, y_true):
        penalty = self.alpha * self.parabolic_penalty(y_true, y_pred)
        if isinstance(self.categorical_crossentropy, nn.CrossEntropyLoss):
            loss = self.categorical_crossentropy(y_pred, y_true.argmax(dim=-1))
        else:
            loss = self.categorical_crossentropy(y_pred, y_true)

        loss = penalty + loss

        if self.reduction == 'sum':
            return t.sum(loss)
        elif self.reduction == 'mean':
            return t.mean(loss)
        else:
            return loss.view(y_pred.shape[0])

