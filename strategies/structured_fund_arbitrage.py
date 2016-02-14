from logbook import Logger, StreamHandler, TimedRotatingFileHandler
import os
import sys

from easyquant import StrategyTemplate


class Strategy(StrategyTemplate):
    def __init__(self, user):
        super().__init__(user)
        self.log = Logger(self.__class__.__name__)
        handler = TimedRotatingFileHandler('/tmp/strategy.log',
                                   date_format='%Y-%m-%d')
        self.log.handlers.append(handler)
        self.log.handlers.append(StreamHandler(sys.stdout))

    def strategy(self, event):
        self.arbitrage(event.data, 502013, 5)

    def arbitrage(self, data, code, level):
        if not self.is_valid_structured_fund(data, code, level):
            return

        origin_fund = str(code)
        a_fund = str(code + 1)
        b_fund = str(code + 2)

        # 确定是分拆套利还是合并套利，分拆套利用的是母基金的卖榜数据和分级基金的买榜数据，合并套利这是相反
        # 判断是否可以进行合并套利：按卖1价买入1份额的a基金和1份额的b基金进行合并，按母基金买1价进行卖出
        if data[origin_fund]['buy'] * 19998 > (data[a_fund]['sell'] + data[b_fund]['sell']) * 10001:
            origin_fund_vol = self.fetch_volume(data, origin_fund, 'bid', level)
            a_fund_vol = self.fetch_volume(data, a_fund, 'ask', level)
            b_fund_vol = self.fetch_volume(data, b_fund, 'ask', level)
            self.merge(data, origin_fund, origin_fund_vol, a_fund, a_fund_vol, b_fund, b_fund_vol, level)
        # 判断是否可以进行拆分套利：按母基金卖1价买入拆分，按买1价卖出1份额的a基金和1份额的b基金
        elif data[origin_fund]['sell'] * 20002 < (data[a_fund]['buy'] + data[b_fund]['buy']) * 9999:
            origin_fund_vol = self.fetch_volume(data, origin_fund, 'ask', level)
            a_fund_vol = self.fetch_volume(data, a_fund, 'bid', level)
            b_fund_vol = self.fetch_volume(data, b_fund, 'bid', level)
            self.split(data, origin_fund, origin_fund_vol, a_fund, a_fund_vol, b_fund, b_fund_vol, level)
        else:
            print('No Chances')

    def merge(self, data, origin_fund, origin_fund_vol, a_fund, a_fund_vol, b_fund, b_fund_vol, level):
        origin_fund_index = 1
        a_fund_index = 1
        b_fund_index = 1

        # 只考虑拟合到一部分的买榜价格和卖榜价格
        while origin_fund_index <= level and a_fund_index <= level and b_fund_index <= level:
            origin_fund_price = float(data[origin_fund][self.bid(origin_fund_index)])
            a_fund_price = float(data[a_fund][self.ask(a_fund_index)])
            b_fund_price = float(data[b_fund][self.ask(b_fund_index)])

            if origin_fund_price * 19998 > (a_fund_price + b_fund_price) * 10001:
                merge_vol, fund = self.min(origin_fund_vol[origin_fund_index], \
                    a_fund_vol[a_fund_index], b_fund_vol[b_fund_index])

                if merge_vol > 0:
                    rate = origin_fund_price * 199.96 / (a_fund_price + b_fund_price) - 100.0
                    self.log.info('Merge Shares: %f, Origin: %f, A: %f, B: %f, Rate: %.2f%%' % \
                                (merge_vol, origin_fund_price, a_fund_price, b_fund_price, rate))

                    origin_fund_vol[origin_fund_index] -= merge_vol
                    a_fund_vol[a_fund_index] -= merge_vol
                    b_fund_vol[b_fund_index] -= merge_vol
                    if fund == 'a':
                        a_fund_index += 1
                    elif fund == 'b':
                        b_fund_index += 1
                    elif fund == 'origin':
                        origin_fund_index += 1

    def split(self, data, origin_fund, origin_fund_vol, a_fund, a_fund_vol, b_fund, b_fund_vol, level):
        origin_fund_index = 1
        a_fund_index = 1
        b_fund_index = 1

        # 只考虑拟合到一部分的买榜价格和卖榜价格
        while origin_fund_index <= level and a_fund_index <= level and b_fund_index <= level:
            origin_fund_price = float(data[origin_fund][self.ask(origin_fund_index)])
            a_fund_price = float(data[a_fund][self.bid(a_fund_index)])
            b_fund_price = float(data[b_fund][self.bid(b_fund_index)])

            if origin_fund_price * 20002 < (a_fund_price + b_fund_price) * 9999:
                split_vol, fund = self.min(origin_fund_vol[origin_fund_index], \
                    a_fund_vol[a_fund_index], b_fund_vol[b_fund_index])

                if split_vol > 0:
                    rate = (a_fund_price + b_fund_price) * 49.99 / origin_fund_price - 100.0
                    self.log.info('Split Shares: %f, Origin: %f, A: %f, B: %f, Rate: %.2f%%' % \
                                (split_vol, origin_fund_price, a_fund_price, b_fund_price, rate))

                    origin_fund_vol[origin_fund_index] -= split_vol
                    a_fund_vol[a_fund_index] -= split_vol
                    b_fund_vol[b_fund_index] -= split_vol
                    if fund == 'a':
                        a_fund_index += 1
                    elif fund == 'b':
                        b_fund_index += 1
                    elif fund == 'origin':
                        origin_fund_index += 1
            else:
                break

    def min(self, origin_fund_vol, a_fund_vol, b_fund_vol):
        vol = 0
        fund = ''
        if origin_fund_vol > a_fund_vol:
            if a_fund_vol > b_fund_vol:
                # 分级b的数量最少
                vol = b_fund_vol
                fund = 'b'
            else:
                # 分级a的数量最少
                vol = a_fund_vol
                fund = 'a'
        else:
            if origin_fund_vol > b_fund_vol:
                # 分级b的数量最少
                vol = b_fund_vol
                fund = 'b'
            else:
                # 母基金的数量最少
                vol = origin_fund_vol
                fund = 'origin'
        return vol, fund

    def bid(self, index):
        return 'bid' + str(index)

    def ask(self, index):
        return 'ask' + str(index)

    # 将买卖数据放入数组中
    def fetch_volume(self, data, code, prefix, level):
        vol = [0] # 填充index=0的数据，方便使用
        for index in range(1, level + 1):
            vol.append(int(data[code][prefix + str(index) + '_volume']))
        return vol

    # 判断母基金、分级a和分级b基金是否都有买卖数据
    def is_valid_structured_fund(self, data, code, level):
        return self.has_valid_data(data, code, 'ask', level) and self.has_valid_data(data, code, 'bid', level) and \
            self.has_valid_data(data, code + 1, 'ask', level) and self.has_valid_data(data, code + 1, 'bid', level) and \
            self.has_valid_data(data, code + 2, 'ask', level) and self.has_valid_data(data, code + 2, 'bid', level)

    # 判断是否有买卖数据
    def has_valid_data(self, data, code, prefix, level):
        flag = str(code) in data
        for index in range(1, level + 1):
            flag &= (prefix + str(index)) in data[str(code)] and \
                (prefix + str(index) + '_volume') in data[str(code)]
        return flag

