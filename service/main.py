import grpc
import time
import argparse
from concurrent import futures
import Ddzai_pb2, Ddzai_pb2_grpc

from douzero.env.game import InfoSet
from douzero.evaluation.deep_agent import DeepAgent
from douzero.env import move_detector as md, move_selector as ms
from douzero.env.move_generator import MovesGener
from douzero.env.game import GameEnv

def get_legal_card_play_actions(player_hand_cards, card_play_action_seq):
    mg = MovesGener(player_hand_cards)

    action_sequence = card_play_action_seq

    rival_move = []
    if len(action_sequence) != 0:
        if len(action_sequence[-1]) == 0:
            rival_move = action_sequence[-2]
        else:
            rival_move = action_sequence[-1]

    rival_type = md.get_move_type(rival_move)
    rival_move_type = rival_type['type']
    rival_move_len = rival_type.get('len', 1)
    moves = list()

    if rival_move_type == md.TYPE_0_PASS:
        moves = mg.gen_moves()

    elif rival_move_type == md.TYPE_1_SINGLE:
        all_moves = mg.gen_type_1_single()
        moves = ms.filter_type_1_single(all_moves, rival_move)

    elif rival_move_type == md.TYPE_2_PAIR:
        all_moves = mg.gen_type_2_pair()
        moves = ms.filter_type_2_pair(all_moves, rival_move)

    elif rival_move_type == md.TYPE_3_TRIPLE:
        all_moves = mg.gen_type_3_triple()
        moves = ms.filter_type_3_triple(all_moves, rival_move)

    elif rival_move_type == md.TYPE_4_BOMB:
        all_moves = mg.gen_type_4_bomb() + mg.gen_type_5_king_bomb()
        moves = ms.filter_type_4_bomb(all_moves, rival_move)

    elif rival_move_type == md.TYPE_5_KING_BOMB:
        moves = []

    elif rival_move_type == md.TYPE_6_3_1:
        all_moves = mg.gen_type_6_3_1()
        moves = ms.filter_type_6_3_1(all_moves, rival_move)

    elif rival_move_type == md.TYPE_7_3_2:
        all_moves = mg.gen_type_7_3_2()
        moves = ms.filter_type_7_3_2(all_moves, rival_move)

    elif rival_move_type == md.TYPE_8_SERIAL_SINGLE:
        all_moves = mg.gen_type_8_serial_single(repeat_num=rival_move_len)
        moves = ms.filter_type_8_serial_single(all_moves, rival_move)

    elif rival_move_type == md.TYPE_9_SERIAL_PAIR:
        all_moves = mg.gen_type_9_serial_pair(repeat_num=rival_move_len)
        moves = ms.filter_type_9_serial_pair(all_moves, rival_move)

    elif rival_move_type == md.TYPE_10_SERIAL_TRIPLE:
        all_moves = mg.gen_type_10_serial_triple(repeat_num=rival_move_len)
        moves = ms.filter_type_10_serial_triple(all_moves, rival_move)

    elif rival_move_type == md.TYPE_11_SERIAL_3_1:
        all_moves = mg.gen_type_11_serial_3_1(repeat_num=rival_move_len)
        moves = ms.filter_type_11_serial_3_1(all_moves, rival_move)

    elif rival_move_type == md.TYPE_12_SERIAL_3_2:
        all_moves = mg.gen_type_12_serial_3_2(repeat_num=rival_move_len)
        moves = ms.filter_type_12_serial_3_2(all_moves, rival_move)

    elif rival_move_type == md.TYPE_13_4_2:
        all_moves = mg.gen_type_13_4_2()
        moves = ms.filter_type_13_4_2(all_moves, rival_move)

    elif rival_move_type == md.TYPE_14_4_22:
        all_moves = mg.gen_type_14_4_22()
        moves = ms.filter_type_14_4_22(all_moves, rival_move)

    if rival_move_type not in [md.TYPE_0_PASS,
                                md.TYPE_4_BOMB, md.TYPE_5_KING_BOMB]:
        moves = moves + mg.gen_type_4_bomb() + mg.gen_type_5_king_bomb()

    if len(rival_move) != 0:  # rival_move is not 'pass'
        moves = moves + [[]]

    for m in moves:
        m.sort()

    return moves

def get_last_move(card_play_action_seq):
    last_move = []
    if len(card_play_action_seq) != 0:
        if len(card_play_action_seq[-1]) == 0:
            last_move = card_play_action_seq[-2]
        else:
            last_move = card_play_action_seq[-1]

    return last_move

def get_last_two_moves(card_play_action_seq):
    last_two_moves = [[], []]
    for card in card_play_action_seq[-2:]:
        last_two_moves.insert(0, card)
        last_two_moves = last_two_moves[:2]
    return last_two_moves

PositionPrevConverter = {
    'landlord': 'landlord_up',
    'landlord_up': 'landlord_down',
    'landlord_down': 'landlord'
}
PositionNextConverter = {
    'landlord': 'landlord_down',
    'landlord_up': 'landlord',
    'landlord_down': 'landlord_up'
}

PlayersADP = {
    'landlord': DeepAgent('landlord', 'baselines/douzero_ADP/landlord.ckpt'),
    'landlord_up': DeepAgent('landlord_up', 'baselines/douzero_ADP/landlord_up.ckpt'),
    'landlord_down': DeepAgent('landlord_down', 'baselines/douzero_ADP/landlord_down.ckpt'),
}

class DdzServicer(Ddzai_pb2_grpc.AIServicer):
    def OnQueryNextPlay(self, request, context):
        current_position = request.my_position #当前座位
        bomb_num = request.bomb_num #炸弹数量
        three_landlord_cards = [v for v in request.three_landlord_cards]
        my_hand_cards = []
        landlord_hand_cards = []
        landlord_up_hand_cards = []
        landlord_down_hand_cards = []
        landlord_played_cards = []
        landlord_up_played_cards = []
        landlord_down_played_cards = []
        card_play_action_seq = []
        for data in request.player_datas:
            hand_cards = [v for v in data.hand_cards]
            played_cards = [v for v in data.played_cards]
            if data.position == 'landlord':
                landlord_hand_cards.extend(hand_cards)
                landlord_played_cards.extend(played_cards)
            elif data.position == 'landlord_up':
                landlord_up_hand_cards.extend(hand_cards)
                landlord_up_played_cards.extend(played_cards)
            elif data.position == 'landlord_down':
                landlord_down_hand_cards.extend(hand_cards)
                landlord_down_played_cards.extend(played_cards)
            if data.position == request.my_position:
                my_hand_cards.extend([v for v in data.hand_cards])
        for t in request.card_play_action_seq:
            card_play_action_seq.append([v for v in t.cards])

        iset = InfoSet(current_position)
        iset.player_hand_cards = my_hand_cards
        iset.num_cards_left_dict = {
            'landlord': len(landlord_hand_cards),
            'landlord_up': len(landlord_up_hand_cards),
            'landlord_down': len(landlord_down_hand_cards)
        }
        iset.three_landlord_cards = three_landlord_cards
        iset.card_play_action_seq = card_play_action_seq
        iset.other_hand_cards = []
        for data in request.player_datas:
            if current_position != data.position:
                iset.other_hand_cards.extend([v for v in data.hand_cards])
        iset.legal_actions = get_legal_card_play_actions(iset.player_hand_cards, iset.card_play_action_seq)
        iset.last_move = get_last_move(iset.card_play_action_seq)
        iset.last_two_moves = get_last_two_moves(iset.card_play_action_seq)
        #每个人最近一次出牌情况
        iset.last_move_dict = {}
        the_position = PositionPrevConverter[current_position]
        seq_len = len(iset.card_play_action_seq)
        for idx in range(0, 3):
            if seq_len > idx:
                iset.last_move_dict[the_position] = iset.card_play_action_seq[-(idx+1)]
            else:
                iset.last_move_dict[the_position] = []
            the_position = PositionPrevConverter[the_position]
        #已出过的牌
        iset.played_cards = {
            'landlord': landlord_played_cards,
            'landlord_up': landlord_up_played_cards,
            'landlord_down': landlord_down_played_cards
        }
        #每个人手牌
        iset.all_handcards = {
            'landlord': landlord_hand_cards,
            'landlord_up': landlord_up_hand_cards,
            'landlord_down': landlord_down_hand_cards
        }
        #上个玩家出牌座位
        if seq_len > 0 and len(iset.card_play_action_seq[-1]) > 0:
            iset.last_pid = PositionPrevConverter[current_position]
        elif seq_len > 1 and len(iset.card_play_action_seq[-2]) > 0:
            iset.last_pid = PositionNextConverter[current_position]
        else:
            iset.last_pid = current_position
        #炸弹数量
        iset.bomb_num = bomb_num

        player = PlayersADP[current_position]
        action = player.act(iset)
        ack = Ddzai_pb2.QueryNextPlayAck(errcode=0, result=action)
        print('出牌：{}'.format(action))
        return ack

    def OnEvaluateReq(self, request, context):
        arr = [
            [v for v in request.pos1_cards],
            [v for v in request.pos2_cards],
            [v for v in request.pos3_cards]
        ]
        three_cards = [v for v in request.three_landlord_cards]
        cards_sequence = [
            {'landlord': arr[0].copy(),
             'landlord_up': arr[2].copy(),
             'landlord_down': arr[1].copy(),
             'three_landlord_cards': three_cards.copy()
            },
            {'landlord': arr[0].copy(),
             'landlord_up': arr[1].copy(),
             'landlord_down': arr[2].copy(),
             'three_landlord_cards': three_cards.copy()
            },
            {'landlord': arr[1].copy(),
             'landlord_up': arr[0].copy(),
             'landlord_down': arr[2].copy(),
             'three_landlord_cards': three_cards.copy()
            },
            {'landlord': arr[1].copy(),
             'landlord_up': arr[2].copy(),
             'landlord_down': arr[0].copy(),
             'three_landlord_cards': three_cards.copy()
            },
            {'landlord': arr[2].copy(),
             'landlord_up': arr[1].copy(),
             'landlord_down': arr[0].copy(),
             'three_landlord_cards': three_cards.copy()
            },
            {'landlord': arr[2].copy(),
             'landlord_up': arr[0].copy(),
             'landlord_down': arr[1].copy(),
             'three_landlord_cards': three_cards.copy()
            },
        ]
        results = []
        for card_play_data in cards_sequence:
            env = GameEnv(PlayersADP)
            env.card_play_init(card_play_data)
            while not env.game_over:
                env.step()
            result = {}
            if env.num_wins['landlord'] > 0:
                result['win_type'] = 1
            else:
                result['win_type'] = 2
            result['boom_count'] = env.bomb_num
            result['landlord_left_count'] = len(env.info_sets['landlord'].player_hand_cards)
            result['landlord_up_left_count'] = len(env.info_sets['landlord_up'].player_hand_cards)
            result['landlord_down_left_count'] = len(env.info_sets['landlord_down'].player_hand_cards)
            results.append(result)
        ack = Ddzai_pb2.EvaluateAck(errcode=0, results=results)
        print('评估：{}'.format(results))
        return ack

def main(port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    servicer = DdzServicer()
    Ddzai_pb2_grpc.add_AIServicer_to_server(servicer, server)
    server.add_insecure_port('0.0.0.0:{}'.format(port))
    server.start()

    print("gRpc start! port={}".format(port))

    while True:
        try:
            time.sleep(30)
        except KeyboardInterrupt:
            print("stopping...")
            server.stop(0)
            break

if __name__ == '__main__':
    parser = argparse.ArgumentParser('Ddzai grpc')
    parser.add_argument('--port', type=int, default=19999)
    args = parser.parse_args()
    main(args.port)
