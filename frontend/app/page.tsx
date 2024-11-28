"use client"

import Image from "next/image";
import { list } from "postcss";
import { useState } from "react";

export default function Home() {

  const [count, setCount] = useState(0)
  const [list, setList] = useState(["eggs", "butter"])
  const [input, setInput] = useState("")

  



  const increment = () => {setCount(count+1)}
  const decrement = () => {setCount(count-1)}


  return (
    <div>
      <button className="border-2 p-3 border-blue-800 bg-yellow-400" onClick={increment}>+</button>
      <button onClick={decrement}>-</button>
      <div>{count}</div>


      {list.map(element => <div>{element}</div>)}
      <input onChange={(e) => {setInput(e.target.value)}} placeholder="enter item" />
      <button onClick={() => {setList(list => [...list, input]); console.log(list)}} >submit</button>

    </div>
  );
}