import os

import torch
import torch.utils.data as data
from PIL import Image
from lxml import etree

from maskrcnn_benchmark.structures.bounding_box import BoxList

VOC_BBOX_LABEL_NAMES = ('aeroplane',
                        'bicycle',
                        'bird',
                        'boat',
                        'bottle',
                        'bus',
                        'car',
                        'cat',
                        'chair',
                        'cow',
                        'diningtable',
                        'dog',
                        'horse',
                        'motorbike',
                        'person',
                        'pottedplant',
                        'sheep',
                        'sofa',
                        'train',
                        'tvmonitor')


class PascalVOC(data.Dataset):
    def __init__(self, data_dir, split, transforms=None):
        self.data_dir = data_dir
        self.split = split
        self.anns_dir = os.path.join(data_dir, 'Annotations')
        self.imgs_dir = os.path.join(data_dir, 'JPEGImages')

        split_file = os.path.join(data_dir, 'ImageSets', 'Main', '%s.txt' % split)
        with open(split_file) as fid:
            self.ids = sorted([l.strip() for l in fid.readlines()])

        self.json_category_id_to_contiguous_id = {
            v: i + 1 for i, v in enumerate(range(20))
        }
        self.contiguous_category_id_to_json_id = {
            v: k for k, v in self.json_category_id_to_contiguous_id.items()
        }
        self.anns = {}
        for img_id in self.ids:
            with open(os.path.join(self.anns_dir, '%s.xml' % img_id)) as fid:
                xml_str = fid.read()
            xml = etree.fromstring(xml_str)
            data = self._recursive_parse_xml_to_dict(xml)['annotation']
            self.anns[img_id] = {
                'boxes': [[int(obj['bndbox']['xmin']),
                           int(obj['bndbox']['ymin']),
                           int(obj['bndbox']['xmax']),
                           int(obj['bndbox']['ymax'])] for obj in data['object'] if int(obj['difficult']) == 0],
                'labels': [VOC_BBOX_LABEL_NAMES.index(obj['name']) for obj in data['object'] if int(obj['difficult']) == 0],
                'size': data['size']
            }

        self.id_to_img_map = {k: v for k, v in enumerate(self.ids)}
        self.transforms = transforms

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, index):
        img_id = self.ids[index]
        img = Image.open(os.path.join(self.imgs_dir, '%s.jpg' % img_id)).convert('RGB')
        ann = self.anns[img_id]
        boxes = ann['boxes']
        labels = ann['labels']

        boxes = torch.as_tensor(boxes).reshape(-1, 4)  # guard against no boxes
        target = BoxList(boxes, img.size, mode="xyxy").convert("xyxy")
        classes = [self.json_category_id_to_contiguous_id[c] for c in labels]
        classes = torch.tensor(classes)
        target.add_field("labels", classes)

        target = target.clip_to_image(remove_empty=True)
        if self.transforms is not None:
            img, target = self.transforms(img, target)

        return img, target, index

    def get_img_info(self, index):
        img_id = self.ids[index]
        ann = self.anns[img_id]
        return ann['size']

    def _recursive_parse_xml_to_dict(self, xml):
        """Recursively parses XML contents to python dict.
        We assume that `object` tags are the only ones that can appear
        multiple times at the same level of a tree.
        Args:
          xml: xml tree obtained by parsing XML file contents using lxml.etree
        Returns:
          Python dictionary holding XML contents.
        """
        if len(xml) == 0:
            return {xml.tag: xml.text}
        result = {}
        for child in xml:
            child_result = self._recursive_parse_xml_to_dict(child)
            if child.tag != 'object':
                result[child.tag] = child_result[child.tag]
            else:
                if child.tag not in result:
                    result[child.tag] = []
                result[child.tag].append(child_result[child.tag])
        return {xml.tag: result}


if __name__ == '__main__':
    pass