from email.mime import image
import numpy as np
from optimization import OCOpt
from Annotations import BBox, predBBox, Annotations, Annotation_images, Prediction_images
import pulp

import json
class OC_Cost:
    def __init__(self, lm=1):
        self.lm = lm

    def getIOU(self, truth: BBox, pred: predBBox):
        a_area = (truth.get_rightbottom_x() - truth.x + 1) * \
            (truth.get_rightbottom_y() - truth.y + 1)
        b_area = (pred.get_rightbottom_x() - pred.x + 1) * \
            (pred.get_rightbottom_y() - pred.y + 1)

        abx_mn = max(truth.x, pred.x)
        aby_mn = max(truth.y, pred.y)
        abx_mx = min(truth.get_rightbottom_x(), pred.get_rightbottom_x())
        aby_mx = min(truth.get_rightbottom_y(), pred.get_rightbottom_y())
        w = max(0, abx_mx - abx_mn + 1)
        h = max(0, aby_mx - aby_mn + 1)
        intersect = w * h

        iou = intersect / (a_area + b_area - intersect)
        return iou

    def getCloc(self, truth: BBox, pred: predBBox):
        """get Cloc

        Args:
            truth (dict): set truth bbox dict
            pred (dict): set pred bbox dict including precision

        Returns:
            float: C_loc
        """
        cost: float = (1 - self.getIOU(truth, pred)) / 2
        return cost

    def getCcls(self, truth: BBox, pred: predBBox):
        """get Ccls

        Args:
            truth (BBox): set truth bbox dict
            pred (predBBox): set pred bbox dict including precision

        Returns:
            float: C_cls
        """
        clt = truth.label
        clp = pred.label

        preci = pred.precision
        ccls = 0.5
        if clt == clp:
            ccls = (1 - preci) / 2
        else:
            ccls = (1 + preci) / 2
        return ccls

    def getoneCost(self, truth, pred):
        """get C_ij cost

        Args:
            truth (dict): set truth bbox dict
            pred (dict): set pred bbox dict including precision

        Returns:
            float: C_ij cost
        """
        Cloc = self.getCloc(truth, pred)
        CCls = self.getCcls(truth, pred)

        return (self.lm * Cloc) + ((1 - self.lm) * CCls)

    def build_C_matrix(self, truth_annotations: Annotations, pred_annotations: Annotations):
        n = len(truth_annotations.bboxs)
        m = len(pred_annotations.bboxs)

        self.cost = np.zeros((m, n))

        for i in range(m):
            for j in range(n):
                self.cost[i][j] = self.getoneCost(
                    truth_annotations.bboxs[j], pred_annotations.bboxs[i])
        return self.cost

    def optim(self):
        m = self.cost.shape[0] + 1
        n = self.cost.shape[1] + 1
        opt = OCOpt(m, n, 0.3)
        opt.set_cost_matrix(self.cost)
        opt.setVariable()
        opt.setObjective()
        opt.setConstrain()

        result = opt.prob.solve()
        p_matrix = np.zeros((m, n))

        print('objective value: {}'.format(pulp.value(opt.prob.objective)))
        print('solution')
        for i in range(opt.m):
            for j in range(opt.n):
                print(
                    f'{opt.variable[j][i]} = {pulp.value(opt.variable[j][i])}')
                p_matrix[j][i] = pulp.value(opt.variable[j][i])
        p_tilda_matrix = p_matrix / np.sum(p_matrix)
        p_tilda_matrix[m - 1][n - 1] = 0
        self.p_matrix = p_matrix
        self.p_tilda_matrix = p_tilda_matrix
        self.opt = opt
        return p_tilda_matrix


if __name__ == "__main__":
    pred_path = "./pred.json"
    truth_path = "./truth.json"
    preds: Prediction_images = Prediction_images()
    truth: Annotation_images = Annotation_images()
    occost = OC_Cost()

    with open(pred_path) as f:
        pd_dict = json.load(f)
        preds.load_from_dict(pd_dict)

    with open(truth_path) as f:
        gt_dict = json.load(f)
        truth.load_from_dict(gt_dict)

    for image_name in truth.keys():
        print(truth[image_name])
        print(preds[image_name])

        c_matrix = occost.build_C_matrix(truth[image_name], preds[image_name])
        pi_tilda_matrix = occost.optim()
        print(pi_tilda_matrix)
        print(occost.opt.cost)

        oc_cost = np.sum(np.multiply(pi_tilda_matrix, occost.opt.cost))
        print(oc_cost)