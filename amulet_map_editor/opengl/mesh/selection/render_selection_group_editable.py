import numpy
from typing import Tuple, Dict, Any, Optional

from amulet.api.data_types import BlockCoordinatesAny, BlockCoordinatesNDArray, PointCoordinatesAny
from .render_selection_group import RenderSelectionGroup
from .render_selection import RenderSelection
from .render_selection_editable import RenderSelectionEditable


class RenderSelectionGroupEditable(RenderSelectionGroup):
    """A group of selection boxes to be drawn with an added editable box."""
    def __init__(self,
                 context_identifier: str,
                 texture_bounds: Dict[Any, Tuple[float, float, float, float]],
                 texture: int
                 ):
        super().__init__(context_identifier, texture_bounds, texture)
        self._editable = True
        self._active_box: Optional[RenderSelectionEditable] = None
        self._active_box_index: Optional[int] = None
        self._last_active_box_index: Optional[int] = None
        self._hover_box_index: Optional[int] = None

        self._cursor_position = numpy.array([0, 0, 0], dtype=numpy.int)

    @property
    def active_box(self) -> Optional[RenderSelectionEditable]:
        return self._active_box

    def _new_editable_render_selection(self):
        return RenderSelectionEditable(self._context_identifier, self._texture_bounds, self._texture)

    def _create_active_box_from_cursor(self):
        # create from the cursor position
        self._active_box = self._new_editable_render_selection()  # create a new render selection
        self._last_active_box_index = self._active_box_index
        self._active_box.point1, self._active_box.point2 = self._cursor_position, self._cursor_position
        self._active_box_index = None

    def _create_active_box(self):
        self._active_box = self._new_editable_render_selection()  # create a new render selection
        self._last_active_box_index = self._active_box_index
        if self._active_box_index is None:
            # create from the cursor position
            self._active_box.point1, self._active_box.point2 = self._cursor_position, self._cursor_position
            self._active_box_index = None
        else:
            # create from the active box
            active_box = self._boxes[self._active_box_index]
            self._active_box.point1, self._active_box.point2 = active_box.point1, active_box.point2
            self._active_box.lock()

    @property
    def editable(self) -> bool:
        """Is the selection open for editing.
        This is not for if the box is being modified."""
        return self._editable

    @editable.setter
    def editable(self, editable: bool):
        self._editable = editable
        if editable and self._active_box_index is not None:
            self._create_active_box()
        else:
            self._active_box: Optional[RenderSelectionEditable] = None

    def deselect_all(self):
        while self._boxes:
            box = self._boxes.pop()
            box.unload()
        self._active_box: Optional[RenderSelectionEditable] = None
        self._active_box_index = self._last_active_box_index = None

    def deselect_active(self):
        if self._active_box_index is not None:
            # If the box already exists in the list
            box = self._boxes.pop(self._active_box_index)
            box.unload()
            if self._boxes:
                if self._active_box_index >= 1:
                    self._active_box_index -= 1
                self._create_active_box()
            else:
                self._active_box = None
                self._active_box_index = self._last_active_box_index = None
        elif self._active_box is not None and self._active_box.is_dynamic and self._last_active_box_index is not None:
            # if the box hasn't been committed yet
            self._active_box_index = self._last_active_box_index

    def update_cursor_position(self, position: BlockCoordinatesAny, box_index: Optional[int]):
        self._cursor_position[:] = position
        self._hover_box_index = box_index
        if self._active_box:
            self._active_box.set_active_point(position)

    def box_select_disable(self):
        """Lock the currently selected box in its current state."""
        if self._active_box is not None and self._active_box.is_dynamic:
            self._box_select_disable()

    def _box_select_disable(self):
        self._active_box.lock()
        if self._active_box_index is None:
            box = self._new_render_selection()
            self._active_box_index = len(self._boxes)
            self._boxes.append(box)
        else:
            box = self._boxes[self._active_box_index]
        box.point1, box.point2 = self._active_box.point1, self._active_box.point2

    def box_select_toggle(self, add_modifier: bool = False) -> Optional[BlockCoordinatesNDArray]:
        """Method called to activate or deactivate the active selection"""
        if self._active_box is None:  # if there is no active selection
            self._create_active_box_from_cursor()
        else:  # if there is an active selection
            if self._active_box.is_static:  # if it is is_static
                if self._hover_box_index == self._active_box_index:  # if the cursor was hovering over the current selection
                    self._active_box.unlock(self._cursor_position)  # unlock it
                    self._last_active_box_index = self._active_box_index
                    return self._cursor_position
                elif self._hover_box_index is not None:  # if hovering over a different selected box
                    self._active_box_index = self._hover_box_index  # activate that selection box
                    self._create_active_box()
                else:  # if no hovered selection box
                    if not add_modifier:
                        self.deselect_all()
                    self._create_active_box_from_cursor()
            else:  # the box was being edited.
                self._box_select_disable()

    def draw(self, transformation_matrix: numpy.ndarray, camera_position: PointCoordinatesAny = None):
        for index, box in enumerate(self._boxes):
            if not self.editable or index != self._active_box_index:
                box.draw(transformation_matrix, camera_position)
        if self._active_box is not None:
            self._active_box.draw(transformation_matrix, camera_position)

    def closest_intersection(self, origin: PointCoordinatesAny, vector: PointCoordinatesAny) -> Tuple[Optional[int], Optional["RenderSelection"]]:
        """
        Returns the index for the closest box in the look vector
        :param origin:
        :param vector:
        :return: Index for the closest box. None if no intersection.
        """
        multiplier = 999999999
        index_return = None
        box_return = None
        for index, box in enumerate(self._boxes):
            if not self.editable or self._active_box is None or self._active_box.is_static or index != self._active_box_index:
                mult = box.intersects_vector(origin, vector)
                if mult is not None and mult < multiplier:
                    multiplier = mult
                    index_return = index
                    box_return = box
        return index_return, box_return
