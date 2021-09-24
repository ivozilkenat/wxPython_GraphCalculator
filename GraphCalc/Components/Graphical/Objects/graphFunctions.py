from MyWx.wx import *

from GraphCalc.Components.Graphical.graphPlanes import Dynamic2DGraphicalPlane
from GraphCalc.Components.Property.property import PropertyObjCategory, GraphicalPanelObject, ExprProperty, FloatProperty, IExprProperty
from GraphCalc.Calc.GraphCalculator import Function2DExpr

from GraphCalc._core.utilities import timeMethod
from GraphCalc._core import vc

from sympy import *

import numpy as np


# todo: utilize this class for defined intervals for functions
class DefinitionArea():
    vCoeff = 10

    def __init__(self, closedInterval, valueAmount=None):
        if len(closedInterval) != 2:
            raise ValueError("Valid interval must be of Type (start, end)")

        self.closedInterval = closedInterval

        if closedInterval != -1:
            if valueAmount is not None:
                self.valueAmount = valueAmount
            else:
                self.valueAmount = abs(int((self.closedInterval[0] - self.closedInterval[1]) * DefinitionArea.vCoeff))
            self.values = np.linspace(*self.closedInterval, self.valueAmount)
        else:
            self.value = None

    def __iter__(self):
        if self.closedInterval == -1:
            return -1  # extra Object ? smth. like infinite interval
        else:
            return iter(self.values)

# Current implementation only for testing purposes / lacks optimization
# class MathFunction():
#     def __init__(self, funcExpression):
#         self._funcExpression = funcExpression

#todo:
#   -defy definition loops

class GraphFunction2D(GraphicalPanelObject, IExprProperty): #MathFunction):
    _basePlane: Dynamic2DGraphicalPlane
    def __init__(self, graphCalculator, functionExpression, definitionArea=None):
        GraphicalPanelObject.__init__(self, category=PropertyObjCategory.FUNCTION)
        IExprProperty.__init__(self, graphCalculator, functionExpression)

        self.definitionArea = definitionArea

        self.valueAmount = None
        self.arguments = None
        self.values = None

        self.getProperty(vc.PROPERTY_NAME).setValue("Funktion2D")

    def setBasePlane(self, plane):
        # Properties must be set here, since update function requires panel
        # todo: use color property
        # todo: is there a design that makes implementing the super method redundant?
        super().setBasePlane(plane)
        self.addProperty(FloatProperty(vc.PROPERTY_FUNC_COEFF, 0.1, updateFunction=self.refreshBasePlane, increment=0.01))
        #todo: distinguish by type of function (e.g linear functions can be drawn with less detail)

        self.addProperty(
           ExprProperty(
               "function_definition",
               self._exprObj,
               self._graphCalc,
               updateFunction=self.refreshBasePlane,
               updateExprFunction=self.redefineAllExpressions
        ))

    def exprIsEvaluable(self):
        expr = self.getProperty("function_definition").getValue()
        # testing if evaluable, by trying to get a number value for x = 1 | x != 0 todo: can values be not continuously
        res = expr.expr().subs(Function2DExpr.argumentSymbol, 1)
        return res.is_number #todo: test this

    def calculateData(self):
        if self.exprIsEvaluable():
            #todo: optimize -> calculate values based on dominant areas of point density
            #   -stop using class attributes
            self.valueAmount = int(self._basePlane.getDBLength() * self.getProperty(vc.PROPERTY_FUNC_COEFF).getValue())

            # completely overhaul argument calculation -> thereby value calculation
            # todo: calculate all arguments, which are expected to give valid results:
            #       -find max -> prevent calculating points out of view -> point density
            #       -calc valid values for expression to prevent invalid arguments

            expr = self.getProperty("function_definition").getValue().expr()

            #   get values for which the function is defined

            expr = lambdify(Function2DExpr.argumentSymbol, expr)

            visibleIntervals = self.findArgsInVisible(expr, 150, precision=0.25)
            print(visibleIntervals)
            if (visibleAmount := len(visibleIntervals)) == 0:
                self.values = None
                return
            else:
                amountPerInterval = int(self.valueAmount / visibleAmount)

            self.arguments = [
                    np.linspace(i[0], i[1], amountPerInterval) for i in visibleIntervals
                ]

            self.values = [
               np.fromiter(map(lambda x: expr(x), interval), dtype=np.float)  for interval in self.arguments
            ]
        else:
            self.values = None

    def inLogicalWbList(self, *values):
        lowerWb, upperWb = self._basePlane.getLogicalWB()
        return [lowerWb <= v <= upperWb for v in values]

    def inLogicalWb(self, *values):
        lowerWb, upperWb = self._basePlane.getLogicalWB()
        return any([lowerWb <= v <= upperWb for v in values])


    def findArgsInVisible(self, callableExpr, checkAmount, precision = 0.01, approximationThreshold=0.1):
        #todo: approxThreshold necessary?
        lowerLimit, upperLimit = self._basePlane.getLogicalDB()
        deltaX = self._basePlane.getLogicalDBLength() / checkAmount
        deltaXAdjust = deltaX * precision

        checkArgs = np.linspace(lowerLimit - deltaXAdjust, upperLimit + deltaXAdjust , checkAmount)
        values = np.fromiter(map(callableExpr, checkArgs), dtype=np.float)

        visibleIntervals = []
        for arg, value in zip(checkArgs, values):
            if self.inLogicalWb(value):
                if visibleIntervals != []:
                    last = visibleIntervals[-1]
                    if last[0] - deltaXAdjust <= arg <= last[1] + deltaXAdjust:
                        continue

                interval = []
                # left side
                outOfDB = False
                newArg = arg - deltaXAdjust
                while self.inLogicalWb(callableExpr(newArg)):
                    newArg -= deltaXAdjust
                    if not lowerLimit-deltaXAdjust < newArg:
                        newArg = lowerLimit-deltaXAdjust
                        outOfDB = True
                        break

                    if visibleIntervals != []:
                        last = visibleIntervals[-1]
                        if last[0] + deltaXAdjust <= newArg:
                            break

                if not outOfDB:
                    assert approximationThreshold <= 1
                    aMin, aMax = newArg - deltaXAdjust, newArg + deltaXAdjust
                    deltaA = aMax - aMin
                    threshold = deltaA*approximationThreshold
                    k = 2
                    newDelta = deltaA / k
                    while abs(newDelta) > threshold:
                        newArg -= newDelta
                        newDelta = deltaA / k
                        if self.inLogicalWb(callableExpr(newArg)):
                            k = -2*k
                        else:
                            k = 2*k

                interval.append(newArg)

                # right side
                outOfDB = False
                newArg = arg + deltaXAdjust
                while self.inLogicalWb(callableExpr(newArg)):
                    newArg += deltaXAdjust
                    if not newArg < upperLimit + deltaXAdjust:
                        newArg = upperLimit+deltaXAdjust
                        outOfDB = True
                        break

                #todo: outsource into method?
                if not outOfDB:
                    assert approximationThreshold <= 1
                    aMin, aMax = newArg - deltaXAdjust, newArg + deltaXAdjust
                    deltaA = aMax - aMin
                    threshold = deltaA*approximationThreshold
                    k = 2
                    newDelta = deltaA / k
                    while abs(newDelta) > threshold:
                        newArg += newDelta
                        newDelta = deltaA / k
                        if self.inLogicalWb(callableExpr(newArg)):
                            k = 2*k
                        else:
                            k = -2*k

                interval.append(newArg)
                visibleIntervals.append(interval)
        return visibleIntervals

    # todo: redundant?
    # to slow
    # def getWBIntersections(self, expression):
    #     lowerY, upperY = self._basePlane.getLogicalWB() #todo: test if working wrong when not mirrored
    #
    #     upperInter = solve(expression-lowerY, quick=True)
    #     lowerInter = solve(expression-upperY, quick=True)
    #     return list(filter(lambda x: x.is_real, upperInter)), list(filter(lambda x: x.is_real, lowerInter))

    # todo: redundant?
    # def calcMaxAndMin(self, expression):
    #     maxs, mins = list(), list()
    #     diff1 = diff(expression, Function2DExpr.argumentSymbol)
    #     diff2 = diff(diff1, Function2DExpr.argumentSymbol)
    #
    #     if not diff2.is_zero:
    #         sol = solve(diff1)
    #         for s in sol:
    #             r = diff2.subs(Function2DExpr.argumentSymbol, s)
    #             if r.is_real:
    #                 if r > 0:
    #                     mins.append(s)
    #                 elif r < 0:
    #                     maxs.append(s)
    #     return maxs, mins

    @GraphicalPanelObject.standardProperties
    def blitUpdate(self, deviceContext, needValueUpdate=True):
        # a lot of redundant calculation, since everything is done twice
        # todo: due to new structure, values should only be recalculated if updated is needed
        if needValueUpdate:
            #todo: optimization for values, which don't have to be computed
            self.calculateData()
        if self.values is None:
            self._drawable = False
            return #-> expression is not evaluable
        else:
            self._drawable = True

        self.draw(deviceContext)

    @GraphicalPanelObject.draw(vc.PROPERTY_COLOR, vc.PROPERTY_DRAW_WIDTH)
    def draw(self, deviceContext):
        for i, interval in enumerate(self.values):
            for j in range(1, len(interval) - 1):

                a0, ax, = self.arguments[i][j-1], self.arguments[i][j]
                v0, vx = self.values[i][j-1], self.values[i][j]

                if any(np.isnan(v) for v in (v0, vx)):  # check if nan in calculated values
                    continue

                x1, y1 = self._basePlane.logicalPointToPx(
                    a0, v0
                )
                x2, y2 = self._basePlane.logicalPointToPx(
                    ax, vx
                )

                # todo: just a quick implementation for testing purposes
                # todo: implement after using logical coordinates
                yBottom, yTop = self._basePlane.wb
                # only check if y, since x is always in db-area
                if yBottom <= y1 <= yTop or yBottom <= y2 <= yTop:
                    deviceContext.DrawLine(
                        *self._basePlane.correctPosition(x1, y1),
                        *self._basePlane.correctPosition(x2, y2)
                    )

